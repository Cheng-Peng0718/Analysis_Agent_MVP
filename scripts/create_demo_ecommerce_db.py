from pathlib import Path
import random

import duckdb
import pandas as pd


def main():
    out_dir = Path("demo_data")
    out_dir.mkdir(exist_ok=True)

    db_path = out_dir / "ecommerce_demo.duckdb"

    if db_path.exists():
        db_path.unlink()

    random.seed(42)

    customers = pd.DataFrame(
        [
            {
                "customer_id": i,
                "region": random.choice(["East", "West", "South", "North"]),
                "segment": random.choice(["Consumer", "Corporate", "Small Business"]),
                "signup_month": random.choice(["2023-01", "2023-02", "2023-03", "2023-04"]),
            }
            for i in range(1, 101)
        ]
    )

    products = pd.DataFrame(
        [
            {"product_id": 1, "category": "Electronics", "price": 300.0},
            {"product_id": 2, "category": "Office Supplies", "price": 35.0},
            {"product_id": 3, "category": "Furniture", "price": 180.0},
            {"product_id": 4, "category": "Accessories", "price": 25.0},
            {"product_id": 5, "category": "Software", "price": 120.0},
        ]
    )

    orders = []
    order_items = []

    for order_id in range(1, 501):
        customer_id = random.randint(1, 100)
        month = random.randint(1, 12)
        day = random.randint(1, 28)
        order_date = f"2024-{month:02d}-{day:02d}"

        orders.append(
            {
                "order_id": order_id,
                "customer_id": customer_id,
                "order_date": order_date,
                "channel": random.choice(["Web", "Mobile", "Sales Rep"]),
            }
        )

        n_items = random.randint(1, 4)

        for _ in range(n_items):
            product = products.sample(1, random_state=random.randint(1, 10_000)).iloc[0]
            quantity = random.randint(1, 5)
            discount = random.choice([0.0, 0.05, 0.10, 0.15])
            gross_revenue = float(product["price"]) * quantity
            net_revenue = gross_revenue * (1 - discount)

            order_items.append(
                {
                    "order_id": order_id,
                    "product_id": int(product["product_id"]),
                    "quantity": quantity,
                    "discount": discount,
                    "net_revenue": round(net_revenue, 2),
                }
            )

    orders = pd.DataFrame(orders)
    order_items = pd.DataFrame(order_items)

    con = duckdb.connect(str(db_path))
    con.execute("CREATE TABLE customers AS SELECT * FROM customers")
    con.execute("CREATE TABLE products AS SELECT * FROM products")
    con.execute("CREATE TABLE orders AS SELECT * FROM orders")
    con.execute("CREATE TABLE order_items AS SELECT * FROM order_items")
    con.close()

    print(f"Created demo database: {db_path}")


if __name__ == "__main__":
    main()