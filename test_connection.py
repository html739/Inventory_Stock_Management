import oracledb

try:
    connection = oracledb.connect(
        user="SYSTEM",
        password="std",
        dsn="localhost:1521/FREEPDB1"
    )

    print("Oracle Database Connected Successfully!")

    connection.close()

except Exception as error:
    print("Connection Failed:")
    print(error)
