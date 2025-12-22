from flask import Flask, render_template, request, redirect, url_for, jsonify, session, send_file
from flask_sqlalchemy import SQLAlchemy
import stripe
from generate_invoice import generate_invoice
from flask_mail import Mail, Message
import os
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from pusher_config_example import pusher_client
from flask_cors import CORS
import joblib
import pandas as pd
import numpy as np
from flask import jsonify



# Charger le modèle sauvegardé
model = joblib.load('model_pipeline.pkl')


app = Flask(__name__)

# Configuration
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///ecommerce.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'd56f3b2c9b1f5a7e8c0d3f7b4e9a2c6d8f1e5b3a7c9d2e4f6b8a1d3c5e7f9'
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'images')
app.config['ALLOWED_EXTENSIONS'] = {'png', 'jpg', 'jpeg', 'gif'}
app.config['SESSION_PERMANENT'] = True
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=1)
# Stripe
stripe.api_key = ""
STRIPE_PUBLIC_KEY = ""

# Mail
app.config['MAIL_SERVER'] = 'smtp.office365.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USERNAME'] = 'lizamezioug03@outlook.com'
app.config['MAIL_PASSWORD'] = 'Liza792003'
mail = Mail(app)




# DB
db = SQLAlchemy(app)


# Models
class Product(db.Model):
    __tablename__ = 'products'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    brand = db.Column(db.String(100))
    bag_style = db.Column(db.String(100))
    skin_type = db.Column(db.String(100))
    inner_material = db.Column(db.String(100))
    major_color = db.Column(db.String(100))
    volume = db.Column(db.Float)
    accessories = db.Column(db.String(200))
    price = db.Column(db.Float)
    stock = db.Column(db.Integer)
    image = db.Column(db.String(200))
    is_auction = db.Column(db.Boolean, default=False)

    auctions = db.relationship('Auction', backref='products', cascade="all, delete")


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True)
    password = db.Column(db.String(200))
    is_admin = db.Column(db.Boolean, default=False)

class Auction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'))
    start_time = db.Column(db.DateTime)
    end_time = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    product = db.relationship('Product')

class Bid(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_email = db.Column(db.String(120))
    auction_id = db.Column(db.Integer, db.ForeignKey('auction.id'))
    amount = db.Column(db.Float)
    bid_time = db.Column(db.DateTime, default=datetime.utcnow)
    auction = db.relationship('Auction')
    
class Order(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_email = db.Column(db.String(120), nullable=False)
    order_date = db.Column(db.DateTime, default=datetime.utcnow)
    total_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, processing, shipped, delivered, cancelled
    
    @property
    def status_label(self):
        status_labels = {
            'pending': 'En attente',
            'processing': 'En traitement',
            'shipped': 'Expédiée',
            'delivered': 'Livrée',
            'cancelled': 'Annulée'
        }
        return status_labels.get(self.status, 'Inconnu')
    
    items = db.relationship('OrderItem', backref='order', lazy=True)

class OrderItem(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('order.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'),nullable=False)
    product_name = db.Column(db.String(100), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    price = db.Column(db.Float, nullable=False)


# Helper function for file uploads
def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']

# Init DB + insert data
with app.app_context():
    db.create_all()
    
    # Create admin user if doesn't exist
    admin_user = User.query.filter_by(email='admin@admin.com').first()
    if not admin_user:
        hashed_password = generate_password_hash('adm1243')
        admin_user = User(email='admin@admin.com', password=hashed_password, is_admin=True)
        db.session.add(admin_user)
        db.session.commit()

    if not Product.query.first():
        sample_products = [
            Product(name="Bag Dior", price=3999.99, image="Dior.jpg", stock=1, is_auction=True),
            Product(name="Bag Chanel", price=2999.99, image="Chanel.jpg", stock=1, is_auction=True),
            Product(name="Bag Gucci", price=2000.00, image="Gucci.jpg", stock=1, is_auction=True),
            Product(name="Bag Louis Vuitton", price=1499.99, image="Louis_Vuitton.jpg", stock=1, is_auction=True)
        ]
        db.session.add_all(sample_products)
        db.session.commit()

    if not Auction.query.first():
        now = datetime.utcnow()
        auction_products = Product.query.filter_by(is_auction=True).all()
        for product in auction_products:
            auction = Auction(
                product_id=product.id,
                start_time=now,
                end_time=now + timedelta(hours=2),
                is_active=True
            )
            db.session.add(auction)
        db.session.commit()

# Routes
@app.route('/')
def index():
    products = Product.query.all()
    cart_items = session.get('cart', {})
    cart_count = sum(cart_items.values())
    return render_template('index.html', products=products, cart_count=cart_count, stripe_public_key=STRIPE_PUBLIC_KEY)

# Authentication routes
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        redirect_to = request.args.get('redirect')  # Récupère la page de destination

        if not email or not password:
            return "Champs manquants", 400

        user = User.query.filter_by(email=email).first()
        
        if user:
            if check_password_hash(user.password, password):
                session['customer_email'] = email
                
                if user.is_admin:
                    return redirect(url_for('admin'))
                
                # Redirige vers la page demandée ou vers l'index par défaut
                if redirect_to:
                    return redirect(url_for(redirect_to))  # Modification clé ici
                return redirect(url_for('index'))
            else:
                return redirect(url_for('login', error='login'))
        else:
            try:
                hashed_password = generate_password_hash(password)
                new_user = User(email=email, password=hashed_password)
                db.session.add(new_user)
                db.session.commit()
                session['customer_email'] = email
                
                if redirect_to:
                    return redirect(url_for(redirect_to))  # Même modification pour l'inscription
                return redirect(url_for('index'))
            except Exception as e:
                return redirect(url_for('login', error='register'))

    return render_template('login.html')

@app.route('/check-auth')
def check_auth():
    if 'customer_email' in session:
        return jsonify({'authenticated': True}), 200
    else:
        return jsonify({'authenticated': False}), 401
###################
# Add this route with your other routes in app.py
@app.route('/verify_email', methods=['POST'])
def verify_email():
    email = request.json.get('email')
    if not email:
        return jsonify({'valid': False, 'message': 'Email is required'}), 400
    
    user = User.query.filter_by(email=email).first()
    if user:
        return jsonify({'valid': True, 'message': 'Email verified'})
    else:
        return jsonify({'valid': False, 'message': 'Email not registered. Please sign up first.'}), 404
###################
# Cart routes
@app.route('/cart')
def cart():
    cart_items = session.get('cart', {})
    cart_data = []
    total_price = 0

    for product_id, quantity in cart_items.items():
        product = Product.query.get(product_id)
        if product:
            total_price += product.price * quantity
            cart_data.append({'product': product, 'quantity': quantity})

    return render_template('cart.html', cart_items=cart_data, total_price=total_price)

@app.route('/add_to_cart/<int:product_id>', methods=['POST'])
def add_to_cart(product_id):
    product = Product.query.get(product_id)
    if not product or product.stock <= 0:
        return jsonify({'error': 'Stock insuffisant'}), 400

    cart = session.get('cart', {})

    if cart.get(str(product_id), 0) >= product.stock:
        return jsonify({'error': 'Stock insuffisant'}), 400

    cart[str(product_id)] = cart.get(str(product_id), 0) + 1
    session['cart'] = cart
    session.modified = True

    return jsonify({'cart_count': sum(cart.values())})

@app.route('/decrease_cart/<int:product_id>', methods=['POST'])
def decrease_cart(product_id):
    if 'cart' in session and str(product_id) in session['cart']:
        session['cart'][str(product_id)] -= 1

        if session['cart'][str(product_id)] <= 0:
            del session['cart'][str(product_id)]

        session.modified = True

    return jsonify({'cart_count': sum(session['cart'].values()) if session.get('cart') else 0})

@app.route('/remove_from_cart/<int:product_id>', methods=['POST'])
def remove_from_cart(product_id):
    if 'cart' in session and str(product_id) in session['cart']:
        del session['cart'][str(product_id)]
        session.modified = True

    return jsonify({'cart_count': sum(session['cart'].values()) if session.get('cart') else 0})

@app.route('/clear_cart')
def clear_cart():
    session.pop('cart', None)
    return redirect(url_for('cart'))

# Stripe checkout
@app.route('/create-checkout-session', methods=['POST'])
def create_checkout_session():
    if 'customer_email' not in session:
        print("❌ Utilisateur non connecté — redirection vers login")
        return redirect(url_for('login', redirect='checkout'))

    cart_items = session.get('cart', {})
    if not cart_items:
        return redirect(url_for('cart'))
        
    line_items = []
    
    for product_id, quantity in cart_items.items():
        product = Product.query.get(product_id)
        if product:
            line_items.append({
                'price_data': {
                    'currency': 'eur',
                    'product_data': {'name': product.name},
                    'unit_amount': int(product.price * 100),
                },
                'quantity': quantity
            })
    
    try:
        checkout_session = stripe.checkout.Session.create(
            payment_method_types=['card'],
            line_items=line_items,
            mode='payment',
            success_url=url_for('success', _external=True),
            cancel_url=url_for('cart', _external=True),
            customer_email=session.get('customer_email')
        )
        return redirect(checkout_session.url, code=303)
    except Exception as e:
        print(f"Erreur Stripe: {e}")
        return redirect(url_for('cart'))

@app.route('/success')
def success():
    cart_items = session.get('cart', {})

    if not cart_items:
        return redirect(url_for('index'))

    customer_email = session.get('customer_email', '')
    if not customer_email:
        return redirect(url_for('login'))
        
    customer_name = customer_email.split('@')[0]  # Utiliser la partie avant @ comme nom par défaut
    
    # Créer une nouvelle commande
    total_price = 0
    order_items = []
    
    for product_id, quantity in cart_items.items():
        product = Product.query.get(product_id)
        if product:
            total_price += product.price * quantity
            order_items.append({
                'product_id': product.id,
                'product_name': product.name,
                'quantity': quantity,
                'price': product.price
            })
            # Mettre à jour le stock
            product.stock -= quantity
    
    # Créer la commande dans la base de données
    order = Order(
        customer_email=customer_email,
        total_amount=total_price,
        status='pending'
    )
    db.session.add(order)
    db.session.flush()  # Pour obtenir l'ID de la commande
    
    # Ajouter les items de la commande
    for item_data in order_items:
        order_item = OrderItem(
            order_id=order.id,
            product_id=item_data['product_id'],
            product_name=item_data['product_name'],
            quantity=item_data['quantity'],
            price=item_data['price']
        )
        db.session.add(order_item)
    
    db.session.commit()

    # Générer la facture
    invoice_items = [{'name': item['product_name'], 'quantity': item['quantity'], 'price': item['price']} for item in order_items]
    invoice_path = generate_invoice(order.id, customer_name, customer_email, invoice_items, total_price)

    # Envoyer la facture par email
    if customer_email:
        try:
            msg = Message("Votre Facture", sender=app.config['MAIL_USERNAME'], recipients=[customer_email])
            msg.body = "Veuillez trouver votre facture ci-jointe."
            with app.open_resource(invoice_path) as fp:
                msg.attach(os.path.basename(invoice_path), "application/pdf", fp.read())
            mail.send(msg)
        except Exception as e:
            print(f"Erreur lors de l'envoi de l'email: {e}")

    session.pop('cart', None)

    return render_template('success.html', invoice_path=invoice_path)

# Auction routes
@app.route('/live_auctions')
def live_auctions():
    auctions = Auction.query.filter_by(is_active=True).all()
    return render_template('live_auctions.html', auctions=auctions)

# History
@app.route('/history')
def history():
    if 'customer_email' not in session:
        return redirect(url_for('login'))
    email = session['customer_email']
    bids = Bid.query.filter_by(user_email=email).all()
    return render_template('history.html', bids=bids)

# Admin routes

@app.route('/admin')
def admin():
    user_email = session.get('customer_email')
    if not user_email:
        return redirect(url_for('login'))
    
    user = User.query.filter_by(email=user_email).first()
    if not user or not user.is_admin:
        return redirect(url_for('login'))
    
    # Get all required data for admin panel
    products = Product.query.all()
    active_auctions = Auction.query.filter(Auction.end_time > datetime.utcnow()).all()
    ended_auctions = Auction.query.filter(Auction.end_time <= datetime.utcnow()).all()
    users = User.query.all()
    orders = Order.query.order_by(Order.order_date.desc()).all()
    
    # Process ended auctions with highest bids
    ended_auctions_result = []
    for auction in ended_auctions:
        highest_bid = Bid.query.filter_by(auction_id=auction.id).order_by(Bid.amount.desc()).first()
        ended_auctions_result.append((auction, highest_bid))
    
    return render_template('admin.html', 
                         products=products,
                         active_auctions=active_auctions,
                         ended_auctions=ended_auctions_result,
                         users=users,
                         orders=orders)

@app.route('/admin/add_product', methods=['POST'])
def admin_add_product():
    if 'customer_email' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    user = User.query.filter_by(email=session['customer_email']).first()
    if not user or not user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        # Récupération des données du formulaire
        name = request.form.get('name')
        brand = request.form.get('brand')
        bag_style = request.form.get('bag_style')
        skin_type = request.form.get('skin_type')
        inner_material = request.form.get('inner_material')
        major_color = request.form.get('major_color')
        volume = float(request.form.get('volume'))
        accessories = request.form.get('accessories')
        price = float(request.form.get('price'))
        stock = int(request.form.get('stock'))
        is_auction = 'is_auction' in request.form

        # Vérification et enregistrement de l'image
        if 'image' not in request.files:
            return jsonify({'error': 'No image provided'}), 400

        image = request.files['image']
        if image.filename == '':
            return jsonify({'error': 'No image selected'}), 400

        if image and allowed_file(image.filename):
            filename = secure_filename(image.filename)
            if not os.path.exists(app.config['UPLOAD_FOLDER']):
                os.makedirs(app.config['UPLOAD_FOLDER'])
            image_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            image.save(image_path)

            # Création de l'objet produit
            product = Product(
                name=name,
                brand=brand,
                bag_style=bag_style,
                skin_type=skin_type,
                inner_material=inner_material,
                major_color=major_color,
                volume=volume,
                accessories=accessories,
                price=price,
                stock=stock,
                image=filename,
                is_auction=is_auction
            )
            db.session.add(product)
            db.session.commit()

            return jsonify({'success': True, 'message': 'Produit ajouté avec succès'})
        else:
            return jsonify({'error': 'Type de fichier invalide'}), 400

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/admin/delete_product/<int:product_id>', methods=['DELETE'])
def delete_product(product_id):
    if 'customer_email' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user = User.query.filter_by(email=session['customer_email']).first()
    if not user or not user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        product = Product.query.get_or_404(product_id)
        
        # Delete associated auctions first
        Auction.query.filter_by(product_id=product_id).delete()
        
        # Delete the product
        db.session.delete(product)
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/update_product/<int:product_id>', methods=['PUT'])
def update_product(product_id):
    if 'customer_email' not in session:
        return jsonify({'error': 'Unauthorized'}), 401

    user = User.query.filter_by(email=session['customer_email']).first()
    if not user or not user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403

    try:
        product = Product.query.get_or_404(product_id)
        data = request.get_json()

        # Mettre à jour tous les champs du formulaire
        product.name = data.get('name', product.name)
        product.price = float(data.get('price', product.price))
        product.stock = int(data.get('stock', product.stock))
        product.major_color = data.get('major_color', product.major_color)
        product.volume = int(data.get('volume', product.volume))
        product.skin_type = data.get('skin_type', product.skin_type)
        product.inner_material = data.get('inner_material', product.inner_material)
        product.accessories = data.get('accessories', product.accessories)
        product.bag_style = data.get('bag_style', product.bag_style)
        product.brand = data.get('brand', product.brand)

        # Checkbox : true/false
        product.is_auction = bool(data.get('is_auction', False))

        db.session.commit()
        return jsonify({'success': True})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/products', methods=['GET'])
def get_all_products():
    try:
        products = Product.query.all()
        product_list = []

        for product in products:
            product_list.append({
                'id': product.id,
                'name': product.name,
                'brand': product.brand,
                'bag_style': product.bag_style,
                'skin_type': product.skin_type,
                'inner_material': product.inner_material,
                'major_color': product.major_color,
                'volume': product.volume,
                'accessories': product.accessories,
                'price': product.price,
                'stock': product.stock,
                'is_auction': product.is_auction,
                'image': url_for('static', filename='images/' + product.image)  # adapte si besoin
            })

        return jsonify({'products': product_list})

    except Exception as e:
        return jsonify({'error': str(e)}), 500




# Admin - Add User
@app.route('/admin/add_user', methods=['POST'])
def admin_add_user():
    if 'customer_email' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user = User.query.filter_by(email=session['customer_email']).first()
    if not user or not user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        email = request.form.get('email')
        password = request.form.get('password')
        is_admin = 'is_admin' in request.form
        
        if not email or not password:
            return jsonify({'error': 'Email and password are required'}), 400
            
        if User.query.filter_by(email=email).first():
            return jsonify({'error': 'Email already exists'}), 400
            
        hashed_password = generate_password_hash(password)
        new_user = User(email=email, password=hashed_password, is_admin=is_admin)
        db.session.add(new_user)
        db.session.commit()
        
        return jsonify({'success': True, 'message': 'User added successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Admin - Delete User
@app.route('/admin/delete_user/<int:user_id>', methods=['DELETE'])
def delete_user(user_id):
    if 'customer_email' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user = User.query.filter_by(email=session['customer_email']).first()
    if not user or not user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        user_to_delete = User.query.get_or_404(user_id)
        
        # Prevent deleting last admin
        if user_to_delete.is_admin and User.query.filter_by(is_admin=True).count() <= 1:
            return jsonify({'error': 'Cannot delete last admin'}), 400
            
        db.session.delete(user_to_delete)
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Admin - Update Order Status
@app.route('/admin/update_order_status', methods=['POST'])
def update_order_status():
    if 'customer_email' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user = User.query.filter_by(email=session['customer_email']).first()
    if not user or not user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        order_id = request.form.get('order_id')
        status = request.form.get('status')
        
        order = Order.query.get_or_404(order_id)
        order.status = status
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500



# Admin - Delete Auction
@app.route('/admin/delete_auction/<int:auction_id>', methods=['DELETE'])
def delete_auction(auction_id):
    if 'customer_email' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user = User.query.filter_by(email=session['customer_email']).first()
    if not user or not user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        auction = Auction.query.get_or_404(auction_id)
        db.session.delete(auction)
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/admin/get_auction_products')
def get_auction_products():
    if 'customer_email' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user = User.query.filter_by(email=session['customer_email']).first()
    if not user or not user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    auction_products = Product.query.filter_by(is_auction=True).all()
    products_data = [{
        'id': p.id,
        'name': p.name
    } for p in auction_products]
    
    return jsonify(products_data)


@app.route('/admin/add_auction', methods=['POST'])
def add_auction():
    if 'customer_email' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    user = User.query.filter_by(email=session['customer_email']).first()
    if not user or not user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        product_id = request.form.get('product_id')
        start_time = datetime.strptime(request.form.get('start_time'), '%Y-%m-%dT%H:%M')
        end_time = datetime.strptime(request.form.get('end_time'), '%Y-%m-%dT%H:%M')
        
        # Check if product exists and is marked for auction
        product = Product.query.get(product_id)
        if not product or not product.is_auction:
            return jsonify({'error': 'Invalid product for auction'}), 400
        
        auction = Auction(
            product_id=product_id,
            start_time=start_time,
            end_time=end_time,
            is_active=True
        )
        db.session.add(auction)
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
###################################################
# Add this with your other admin routes
@app.route('/admin/get_user/<int:user_id>')
def get_user(user_id):
    if 'customer_email' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    admin_user = User.query.filter_by(email=session['customer_email']).first()
    if not admin_user or not admin_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    user = User.query.get_or_404(user_id)
    return jsonify({
        'id': user.id,
        'email': user.email,
        'is_admin': user.is_admin
    })

@app.route('/admin/update_user/<int:user_id>', methods=['PUT'])
def update_user(user_id):
    if 'customer_email' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    admin_user = User.query.filter_by(email=session['customer_email']).first()
    if not admin_user or not admin_user.is_admin:
        return jsonify({'error': 'Unauthorized'}), 403
    
    try:
        user = User.query.get_or_404(user_id)
        data = request.get_json()
        
        # Prevent modifying the last admin
        if user.is_admin and User.query.filter_by(is_admin=True).count() <= 1:
            return jsonify({'error': 'Cannot modify last admin'}), 400
        
        if 'email' in data:
            # Check if email already exists
            if data['email'] != user.email and User.query.filter_by(email=data['email']).first():
                return jsonify({'error': 'Email already exists'}), 400
            user.email = data['email']
        
        if 'is_admin' in data:
            # Prevent removing admin status from last admin
            if user.is_admin and not data['is_admin'] and User.query.filter_by(is_admin=True).count() <= 1:
                return jsonify({'error': 'Cannot remove last admin'}), 400
            user.is_admin = bool(data['is_admin'])
        
        if 'password' in data and data['password']:
            user.password = generate_password_hash(data['password'])
        
        db.session.commit()
        return jsonify({
            'success': True,
            'user': {
                'id': user.id,
                'email': user.email,
                'is_admin': user.is_admin
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

#############################################
@app.route('/auction/<int:product_id>')
def auction_detail(product_id):
    product = Product.query.get_or_404(product_id)
    if not product.is_auction:
        return "Ce produit n'est pas une enchère", 404
        
    auction = Auction.query.filter_by(product_id=product_id).first()
    if not auction:
        return "Aucune enchère trouvée pour ce produit", 404
        
    if auction.is_active:
        return render_template('auction_detail.html', auction=auction, product=product)
    else:
        return "Cette enchère a déjà été terminée.", 404
    


@app.route('/place_bid/<int:product_id>', methods=['POST'])
def place_bid(product_id):
    if 'customer_email' not in session:
        return jsonify({'error': 'Connectez-vous pour participer'}), 401
        
    product = Product.query.get_or_404(product_id)
    if not product.is_auction:
        return jsonify({'error': 'Ce produit ne supporte pas les enchères'}), 400
        
    auction = Auction.query.filter_by(product_id=product_id).first()
    if not auction or not auction.is_active:
        return jsonify({'error': 'Enchère non disponible'}), 400
        
    data = request.json
    amount = float(data.get('amount'))
    
    # Vérifier que l'enchère est supérieure au prix de départ et à la dernière enchère
    last_bid = Bid.query.filter_by(auction_id=auction.id).order_by(Bid.amount.desc()).first()
    min_bid = product.price if not last_bid else last_bid.amount + 1
    
    if amount < min_bid:
        return jsonify({'error': f'Votre enchère doit être au moins de {min_bid}€'}), 400
    
    email = session.get('customer_email')
    bid = Bid(user_email=email, auction_id=auction.id, amount=amount)
    db.session.add(bid)
    db.session.commit()
    
    pusher_client.trigger(f"auction-{auction.id}", "new-bid", {
        'email': email, 
        'amount': amount,
        'product_name': product.name
    })
    
    return jsonify({'success': True, 'message': 'Enchère placée avec succès'}) 
    
@app.route('/profile')
def profile():
    if 'customer_email' not in session:
        return redirect(url_for('login', redirect='profile'))
    
    email = session['customer_email']
    user = User.query.filter_by(email=email).first()
    
    if not user:
        return redirect(url_for('login'))
    
    # Récupération des commandes de l'utilisateur
    orders = Order.query.filter_by(customer_email=email).order_by(Order.order_date.desc()).all()
    
    # Récupération des enchères auxquelles l'utilisateur a participé
    user_bids = Bid.query.filter_by(user_email=email).all()
    auction_ids = set([bid.auction_id for bid in user_bids])
    
    participated_auctions = []
    for auction_id in auction_ids:
        auction = Auction.query.get(auction_id)
        if auction:
            # Récupérer la meilleure offre de l'utilisateur pour cette enchère
            my_best_bid = Bid.query.filter_by(user_email=email, auction_id=auction_id).order_by(Bid.amount.desc()).first()
            
            # Récupérer la meilleure offre globale pour cette enchère
            highest_bid = Bid.query.filter_by(auction_id=auction_id).order_by(Bid.amount.desc()).first()
            
            # Vérifier si l'utilisateur est le gagnant d'une enchère terminée
            is_winner = False
            if not auction.is_active and highest_bid and highest_bid.user_email == email:
                is_winner = True
            
            auction_data = {
                'auction': auction,
                'my_best_bid': my_best_bid,
                'highest_bid': highest_bid,
                'is_winner': is_winner
            }
            participated_auctions.append(auction_data)
    
    # Tri des enchères (actives en premier, puis par date de fin)
    participated_auctions.sort(key=lambda x: (not x['auction'].is_active, x['auction'].end_time), reverse=False)
    
    return render_template('profile.html', 
                          user=user, 
                          orders=orders, 
                          participated_auctions=participated_auctions)

@app.route('/profile/update_info', methods=['POST'])
def update_info():
    if 'customer_email' not in session:
        return redirect(url_for('login'))
    
    current_email = session['customer_email']
    new_email = request.form.get('email')
    
    if not new_email:
        return redirect(url_for('profile', message='Email invalide', type='error'))
    
    user = User.query.filter_by(email=current_email).first()
    
    if not user:
        return redirect(url_for('login'))
    
    # Vérifier si le nouvel email existe déjà pour un autre utilisateur
    if new_email != current_email and User.query.filter_by(email=new_email).first():
        return redirect(url_for('profile', message='Cet email est déjà utilisé', type='error'))
    
    # Mettre à jour l'email
    user.email = new_email
    session['customer_email'] = new_email
    
    # Mettre à jour aussi l'email dans les autres tables référençant cet utilisateur
    # Par exemple, les enchères et les commandes
    Bid.query.filter_by(user_email=current_email).update({'user_email': new_email})
    Order.query.filter_by(customer_email=current_email).update({'customer_email': new_email})
    
    try:
        db.session.commit()
        return redirect(url_for('profile', message='Informations mises à jour avec succès', type='success'))
    except Exception as e:
        db.session.rollback()
        return redirect(url_for('profile', message='Une erreur est survenue: ' + str(e), type='error'))

@app.route('/profile/update_password', methods=['POST'])
def update_password():
    if 'customer_email' not in session:
        return redirect(url_for('login'))
    
    email = session['customer_email']
    current_password = request.form.get('current_password')
    new_password = request.form.get('new_password')
    confirm_password = request.form.get('confirm_password')
    
    if not current_password or not new_password or not confirm_password:
        return redirect(url_for('profile', message='Tous les champs sont requis', type='error'))
    
    if new_password != confirm_password:
        return redirect(url_for('profile', message='Les nouveaux mots de passe ne correspondent pas', type='error'))
    
    user = User.query.filter_by(email=email).first()
    
    if not user or not check_password_hash(user.password, current_password):
        return redirect(url_for('profile', message='Mot de passe actuel incorrect', type='error'))
    
    # Mettre à jour le mot de passe
    user.password = generate_password_hash(new_password)
    
    try:
        db.session.commit()
        return redirect(url_for('profile', message='Mot de passe modifié avec succès', type='success'))
    except Exception as e:
        db.session.rollback()
        return redirect(url_for('profile', message='Une erreur est survenue: ' + str(e), type='error'))

@app.route('/download_invoice/<int:order_id>')
def download_invoice(order_id):
    if 'customer_email' not in session:
        return redirect(url_for('login'))
    
    email = session['customer_email']
    order = Order.query.get_or_404(order_id)
    
    # Vérifier que l'utilisateur est bien le propriétaire de la commande
    if order.customer_email != email:
        return "Non autorisé", 403
    
    # Récupérer les items de la commande pour la facture
    items = []
    for item in order.items:
        items.append({
            'name': item.product_name,
            'quantity': item.quantity,
            'price': item.price
        })
    
    # Générer la facture
    customer_name = email.split('@')[0]  # Utiliser la partie avant @ comme nom par défaut
    invoice_path = generate_invoice(order.id, customer_name, email, items, order.total_amount)
    
    return send_file(invoice_path, as_attachment=True)

@app.route('/logout')
def logout():
    # Efface les données de session
    session.pop('customer_email', None)
    session.pop('cart', None)
    # Redirige vers la page d'accueil
    return redirect(url_for('index'))







@app.route('/predict', methods=['POST'])
def predict():
    data = request.get_json()

    # Créer un DataFrame avec les bons noms de colonnes
    features_df = pd.DataFrame([{
        'brand': data['brand'],
        'bag style': data['bag_style'],
        'skin type': data['skin_type'],
        'inner material': data['inner_material'],
        'major color': data['major_color'],
        'volume': data['volume'],
        'accessories': data['accessories']
    }])

    # Prédiction
    predicted_price = model.predict(features_df)

    return jsonify(predicted_price=predicted_price[0])



if __name__ == '__main__':
    CORS(app)
    if not os.path.exists(app.config['UPLOAD_FOLDER']):
        os.makedirs(app.config['UPLOAD_FOLDER'])
    app.run(debug=True)