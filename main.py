from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse
import json
from io import BytesIO

import oracledb
import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt


# ---------------- CONFIGURATION ----------------

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = BASE_DIR / "frontend"

DB_USER = "SYSTEM"
DB_PASSWORD = "std"
DB_DSN = "localhost:1521/FREEPDB1"


# ---------------- DATABASE CONNECTION ----------------

def get_connection():
    return oracledb.connect(
        user=DB_USER,
        password=DB_PASSWORD,
        dsn=DB_DSN
    )


# ---------------- PRODUCT FUNCTIONS ----------------

def get_products():
    connection = get_connection()

    try:
        cursor = connection.cursor()

        cursor.execute("""
            SELECT PRODUCT_ID, PRODUCT_NAME, CATEGORY, QUANTITY, PRICE
            FROM PRODUCTS
            ORDER BY PRODUCT_ID
        """)

        rows = cursor.fetchall()

        return [
            {
                "id": row[0],
                "name": row[1],
                "category": row[2],
                "quantity": row[3],
                "price": float(row[4])
            }
            for row in rows
        ]

    finally:
        connection.close()


# ---------------- WEBSITE REQUEST HANDLER ----------------

class InventoryHandler(SimpleHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        super().__init__(
            *args,
            directory=str(FRONTEND_DIR),
            **kwargs
        )

    def send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")

        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()

        self.wfile.write(body)

    def do_GET(self):

        path = urlparse(self.path).path

        if path == "/":
            self.path = "/index.html"
            super().do_GET()
            return

        if path == "/api/products":
            try:
                self.send_json(get_products())
            except Exception as error:
                print("Database error:", error)
                self.send_json(
                    {"error": "Could not load products from database"},
                    500
                )
            return

        if path == "/stock-graph.png":
            try:
                products = get_products()

                names = [p["name"] for p in products]
                quantities = [p["quantity"] for p in products]

                fig, ax = plt.subplots(figsize=(9, 4.5))

                if products:
                    ax.bar(names, quantities)
                    ax.set_title("Inventory Stock Overview")
                    ax.set_xlabel("Products")
                    ax.set_ylabel("Stock Quantity")
                    ax.tick_params(axis="x", labelrotation=30)
                    fig.tight_layout()
                else:
                    ax.text(
                        0.5, 0.5,
                        "Add products to view the stock graph",
                        ha="center",
                        va="center",
                        transform=ax.transAxes
                    )
                    ax.set_axis_off()

                image = BytesIO()
                fig.savefig(
                    image,
                    format="png",
                    bbox_inches="tight"
                )
                plt.close(fig)

                image_data = image.getvalue()

                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header(
                    "Content-Length",
                    str(len(image_data))
                )
                self.end_headers()
                self.wfile.write(image_data)

            except Exception as error:
                print("Graph error:", error)
                self.send_error(500, "Could not generate stock graph")

            return

        super().do_GET()

    def do_POST(self):

        path = urlparse(self.path).path

        if not path.startswith("/api/"):
            self.send_error(404)
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            data = json.loads(self.rfile.read(length))
            action = path.rstrip("/").split("/")[-1]

            # -------- ADD PRODUCT --------

            if action == "products":

                name = str(data.get("name", "")).strip()
                category = str(data.get("category", "")).strip()
                quantity = data.get("quantity")
                price = data.get("price")

                if (
                    not name
                    or not category
                    or type(quantity) is not int
                    or quantity < 0
                    or type(price) not in (int, float)
                    or price <= 0
                ):
                    self.send_json(
                        {"error": "Invalid product details"},
                        400
                    )
                    return

                connection = get_connection()

                try:
                    cursor = connection.cursor()

                    cursor.execute("""
                        SELECT NVL(MAX(PRODUCT_ID), 0) + 1
                        FROM PRODUCTS
                    """)

                    product_id = cursor.fetchone()[0]

                    cursor.callproc(
                        "ADD_PRODUCT",
                        [
                            product_id,
                            name,
                            category,
                            quantity,
                            price
                        ]
                    )

                finally:
                    connection.close()

                self.send_json(
                    {
                        "id": product_id,
                        "name": name,
                        "category": category,
                        "quantity": quantity,
                        "price": price
                    },
                    201
                )
                return

            # -------- STOCK IN / STOCK OUT --------

            elif action in ("stock-in", "stock-out"):

                product_id = data.get("id")
                quantity = data.get("quantity")

                if (
                    type(product_id) is not int
                    or type(quantity) is not int
                    or quantity <= 0
                ):
                    self.send_json(
                        {"error": "Invalid product ID or quantity"},
                        400
                    )
                    return

                connection = get_connection()

                try:
                    cursor = connection.cursor()

                    cursor.execute("""
                        SELECT PRODUCT_ID
                        FROM PRODUCTS
                        WHERE PRODUCT_ID = :product_id
                    """, {"product_id": product_id})

                    if cursor.fetchone() is None:
                        self.send_json(
                            {"error": "Product not found"},
                            404
                        )
                        return

                    if action == "stock-in":
                        cursor.callproc(
                            "STOCK_IN",
                            [product_id, quantity]
                        )
                    else:
                        cursor.callproc(
                            "STOCK_OUT",
                            [product_id, quantity]
                        )

                finally:
                    connection.close()

                updated_products = get_products()

                updated_product = next(
                    (
                        p for p in updated_products
                        if p["id"] == product_id
                    ),
                    None
                )

                self.send_json(updated_product)
                return

            # -------- DELETE PRODUCT --------

            elif action == "delete":

                product_id = data.get("id")

                if type(product_id) is not int:
                    self.send_json(
                        {"error": "Invalid product ID"},
                        400
                    )
                    return

                connection = get_connection()

                try:
                    cursor = connection.cursor()

                    cursor.execute("""
                        SELECT PRODUCT_ID
                        FROM PRODUCTS
                        WHERE PRODUCT_ID = :product_id
                    """, {"product_id": product_id})

                    if cursor.fetchone() is None:
                        self.send_json(
                            {"error": "Product not found"},
                            404
                        )
                        return

                    # Remove related records first because of foreign keys.
                    # Note: deleting a product also deletes its related logs.
                    cursor.execute("""
                        DELETE FROM STOCK_HISTORY
                        WHERE PRODUCT_ID = :product_id
                    """, {"product_id": product_id})

                    cursor.execute("""
                        DELETE FROM AUDIT_LOG
                        WHERE PRODUCT_ID = :product_id
                    """, {"product_id": product_id})

                    cursor.execute("""
                        DELETE FROM PRODUCTS
                        WHERE PRODUCT_ID = :product_id
                    """, {"product_id": product_id})

                    connection.commit()

                finally:
                    connection.close()

                self.send_json({"message": "Product deleted"})
                return

            else:
                self.send_error(404)

        except (ValueError, TypeError, json.JSONDecodeError):
            self.send_json({"error": "Invalid request"}, 400)

        except oracledb.DatabaseError as error:
            print("Oracle database error:", error)
            self.send_json(
                {"error": "Database operation failed. Check the terminal."},
                500
            )

        except Exception as error:
            print("Server error:", error)
            self.send_json({"error": "Server error"}, 500)


# ---------------- START SERVER ----------------

print("Inventory website running at http://127.0.0.1:8000")
HTTPServer(("127.0.0.1", 8000), InventoryHandler).serve_forever()
