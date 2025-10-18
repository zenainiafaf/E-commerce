import sqlite3
from datetime import datetime, timedelta

# Connexion à la base de données
conn = sqlite3.connect('ecommerce.db')
cursor = conn.cursor()

# Activation des clés étrangères
cursor.execute("PRAGMA foreign_keys = ON;")

# Création de la table des produits avec tous les attributs nécessaires
cursor.execute('''
    CREATE TABLE IF NOT EXISTS products (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        price REAL NOT NULL,
        stock INTEGER NOT NULL CHECK(stock >= 0),
        image TEXT DEFAULT 'placeholder.jpg',
        is_auction INTEGER DEFAULT 0 CHECK(is_auction IN (0,1)),
        brand TEXT,
        bag_style TEXT,
        skin_type TEXT,
        inner_material TEXT,
        major_color TEXT,
        volume TEXT,
        accessories TEXT
    )
''')
print("✅ Table 'products' créée ou existante avec tous les attributs.")

# Création de la table des enchères
cursor.execute('''
    CREATE TABLE IF NOT EXISTS auction (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        product_id INTEGER NOT NULL,
        start_time TEXT,
        end_time TEXT,
        is_active INTEGER DEFAULT 1,
        FOREIGN KEY(product_id) REFERENCES products(id)
    )
''')
print("✅ Table 'auction' créée ou existante.")

# Vérifie s’il y a déjà des produits
cursor.execute("SELECT COUNT(*) FROM products")
if cursor.fetchone()[0] == 0:
    cursor.executemany('''
        INSERT INTO products (
            name, price, stock, image, is_auction, brand, bag_style, skin_type,
            inner_material, major_color, volume, accessories
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', [
        ("Bag Dior", 1000, 1, "Dior.jpg", 0, "Dior", "Tote", "Leather", "Silk", "Beige", "Medium", "Gold Chain"),
        ("Bag Chanel", 0, 1, "Chanel.jpg", 1, "Chanel", "Shoulder", "Caviar", "Canvas", "Black", "Small", "Pearl"),
        ("Bag Gucci", 0, 1, "Gucci.jpg", 1, "Gucci", "Clutch", "Suede", "Velvet", "Red", "Mini", "Zipper"),
        ("Bag Louis Vuitton", 0, 1, "Louis_Vuitton.jpg", 1, "Louis Vuitton", "Satchel", "Monogram", "Linen", "Brown", "Large", "Lock")
    ])
    conn.commit()
    print("✅ Produits insérés dans la base de données.")

    # Création des enchères pour les produits en mode enchère
    cursor.execute("SELECT id FROM products WHERE is_auction = 1")
    now = datetime.utcnow()
    cursor.executemany('''
        INSERT INTO auction (product_id, start_time, end_time, is_active)
        VALUES (?, ?, ?, ?)
    ''', [
        (product_id[0], now.isoformat(), (now + timedelta(minutes=30)).isoformat(), 1)
        for product_id in cursor.fetchall()
    ])
    conn.commit()
    print("✅ Enchères créées pour les sacs de luxe.")
else:
    print("ℹ️ Produits déjà présents, aucun ajout nécessaire.")

conn.close()
print("✅ Base de données prête et complète !")
