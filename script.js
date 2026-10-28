let products = [];

const productForm = document.getElementById("productForm");
const productTable = document.getElementById("productTable");
const searchInput = document.getElementById("searchInput");

async function api(url, data) {
    const response = await fetch(url, {
        method: data ? "POST" : "GET",
        headers: { "Content-Type": "application/json" },
        body: data ? JSON.stringify(data) : undefined
    });

    const result = await response.json();

    if (!response.ok) {
        throw new Error(result.error || "Something went wrong");
    }

    return result;
}

async function loadProducts() {
    try {
        products = await api("/api/products");
        renderProducts();
    } catch (error) {
        alert("Python backend se connection nahi ho raha. Server check karo.");
    }
}

productForm.addEventListener("submit", async function (event) {
    event.preventDefault();

    const data = {
        name: document.getElementById("productName").value.trim(),
        category: document.getElementById("category").value.trim(),
        quantity: Number(document.getElementById("quantity").value),
        price: Number(document.getElementById("price").value)
    };

    if (!data.name || !data.category ||
        !Number.isInteger(data.quantity) || data.quantity < 0 ||
        !Number.isFinite(data.price) || data.price <= 0) {
        alert("Please enter valid product details.");
        return;
    }

    try {
        await api("/api/products", data);
        productForm.reset();
        await loadProducts();
        alert("Product added successfully!");
    } catch (error) {
        alert(error.message);
    }
});

async function updateStock(id, action) {
    const product = products.find(p => p.id === id);
    if (!product) return;

    const input = prompt("Enter quantity:");
    if (input === null || input.trim() === "") return;

    const quantity = Number(input);

    if (!Number.isInteger(quantity) || quantity <= 0) {
        alert("Enter a valid positive quantity.");
        return;
    }

    try {
        await api("/api/" + action, { id, quantity });
        await loadProducts();
        alert("Stock updated successfully!");
    } catch (error) {
        alert(error.message);
    }
}

async function deleteProduct(id) {
    const product = products.find(p => p.id === id);
    if (!product || !confirm("Delete " + product.name + "?")) return;

    try {
        await api("/api/delete", { id });
        await loadProducts();
        alert("Product deleted successfully!");
    } catch (error) {
        alert(error.message);
    }
}

function renderProducts() {
    const search = searchInput.value.trim().toLowerCase();

    const filtered = products.filter(p =>
        p.name.toLowerCase().includes(search) ||
        p.category.toLowerCase().includes(search) ||
        String(p.id).includes(search)
    );

    productTable.innerHTML = "";

    filtered.forEach(p => {
        const status = p.quantity === 0 ? "Out of Stock" :
            p.quantity <= 5 ? "Low Stock" : "In Stock";

        const row = document.createElement("tr");

        [
            p.id, p.name, p.category, p.quantity,
            "₹" + p.price.toFixed(2),
            "₹" + (p.quantity * p.price).toFixed(2)
        ].forEach(value => {
            const cell = document.createElement("td");
            cell.textContent = value;
            row.appendChild(cell);
        });

        const statusCell = document.createElement("td");
        const badge = document.createElement("span");
        badge.className = "status " +
            (p.quantity === 0 ? "out-stock" :
             p.quantity <= 5 ? "low-stock" : "in-stock");
        badge.textContent = status;
        statusCell.appendChild(badge);
        row.appendChild(statusCell);

        const actions = document.createElement("td");

        [
            ["Stock In", () => updateStock(p.id, "stock-in")],
            ["Stock Out", () => updateStock(p.id, "stock-out")],
            ["Delete", () => deleteProduct(p.id)]
        ].forEach(([label, callback]) => {
            const button = document.createElement("button");
            button.textContent = label;
            button.className = "action-btn";
            button.addEventListener("click", callback);
            actions.appendChild(button);
        });

        row.appendChild(actions);
        productTable.appendChild(row);
    });

    document.getElementById("emptyMessage").style.display =
        filtered.length ? "none" : "block";

    document.getElementById("totalProducts").textContent = products.length;

    document.getElementById("totalStock").textContent =
        products.reduce((sum, p) => sum + p.quantity, 0);

    document.getElementById("lowStock").textContent =
        products.filter(p => p.quantity <= 5).length;

    document.getElementById("totalValue").textContent =
        "₹" + products.reduce(
            (sum, p) => sum + p.quantity * p.price, 0
        ).toFixed(2);

    const low = products.filter(p => p.quantity <= 5);

    document.getElementById("stockMessage").textContent =
        low.length
            ? "Low stock: " + low.map(p =>
                p.name + " (" + p.quantity + ")"
              ).join(", ")
            : "No stock alerts.";
            const chart = document.getElementById("stockChart");

if (chart) {
    chart.src = "/stock-graph.png?t=" + Date.now();
}
}

searchInput.addEventListener("input", renderProducts);
loadProducts();
