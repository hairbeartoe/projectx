import os
from flask import render_template, redirect,url_for,send_from_directory, request, send_file, flash
from app import app, db
from app.models import User,Site, Image, subscriptions, Team, Collection
from app.forms import LoginForm, RegisterForm, AddSiteForm, EditUserProfile, AddImagetoCollection, CreateCollectionForm
from flask_bootstrap import Bootstrap
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from sqlalchemy import Date, cast, desc
from flask_images import resized_img_src , Images
from datetime import datetime
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, SignatureExpired
import datetime


images=Images(app)
app.config['UPLOAD_FOLDER'] = 'uploads'

mail = Mail(app)
s = URLSafeTimedSerializer("this-is-secret")

bootstrap = Bootstrap(app)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


@app.route('/')
@app.route('/index')
def index():
    user = {'nickname': 'Eddie'}
    return render_template("index.html",
                           title='Home',
                           user=user)


@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is not None:
            if check_password_hash(user.password,form.password.data):
                login_user(user, remember=form.remember.data)
                return redirect(url_for('dashboard'))
        return "Invalid password or username"
    return render_template('login.html', form=form)


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    form = RegisterForm()
    if form.validate_on_submit():
        # send the confirmation email
        email = form.email.data
        token = s.dumps(email, salt='email-confirm')
        msg = Message('Confirm Email', sender='e.eddieflores@gmail.com', recipients=[email])
        the_link = url_for('confirm_email', token=token, _external=True)
        msg.html = render_template('/email-confirmation.html', link=the_link)
        mail.send(msg)
        # Generate the hashed password
        hashed_password= generate_password_hash(form.password.data, 'sha256')
        # add the new user to the database
        new_user = User(nickname=form.username.data, email=form.email.data, password=hashed_password)
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('dashboard'))
    return render_template('signup.html', form=form)


@app.route('/confirm/<token>')
def confirm_email(token):
    try:
        email = s.loads(token, salt='email-confirm', max_age=120)
        user = User.query.filter(User.email == email).first()
        user.confirmed_email = True
        db.session.commit()
    except SignatureExpired:
        return 'The link is expired'
    return redirect(url_for('dashboard'))




@app.route('/dashboard')
@login_required
def dashboard():
    sites = Site.query.join(Team.subscriptions).filter(Team.id == current_user.team).all()
    if sites is None:
        sites = "this is not cool"
    return render_template('dashboard.html', nickname=current_user.nickname, sites=sites, title='Dashboard')


@app.route('/profile', methods=['GET', 'POST'])
def edit_user_profile():
    form = EditUserProfile(user=current_user)
    user = current_user
    team = Team.query.filter(Team.id == current_user.team).first()
    if form.validate_on_submit():
        user.email = form.email.data
        user.first_name = form.first_name.data
        user.last_name = form.last_name.data
        user.street_address = form.street_address.data
        user.city = form.city.data
        user.state = form.state.data
        user.postal_code = form.postal_code.data
        db.session.commit()
        flash('Profile Updated', category='info')
        return redirect(url_for('edit_user_profile'))
    return render_template('user.html', form=form, title='Profile', user=user, team=team)



@app.route('/screenshots')
def get_sites():
    sites = Site.query.join(Team.subscriptions).filter(Team.id == current_user.team).all()
    if sites is None:
        sites = "this is not cool"
    return render_template('screenshots.html', nickname=current_user.nickname, sites=sites, title='Screenshots')


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))


@app.route('/dates')
def get_dates():
    domain = request.args.get('domain')
    #sites = []
    #for site in Site.query.join(User.subscriptions).filter(User.id == current_user.id).all():
        #sites.append(site.domain)
    dates = set()
    image_names =[]
    images = Image.query.join(Site.images).filter(Site.domain == domain).order_by(desc(Image.date)).all()
    for image in images:
        imagedate = str(image.date)
        imagedate = datetime.strptime(imagedate, '%Y-%m-%d %H:%M:%S').strftime('%B %d, %Y')
        dates.add(imagedate)
        image_names.append(image.name)
    return render_template('dates.html', nickname=current_user.nickname, image_names=images, site=domain, dates=dates)



@app.route('/images', methods=['GET', 'POST'])
def get_images():
    domain = request.args.get('site')
    date = request.args.get('date')
    images = Image.query.join(Site.images).filter(Site.domain == domain, cast(Image.date, Date) == date).all()

    dates = set()
    image_names =[]
    picked_date = date
    #picked_date = datetime.strptime(date, '%Y-%m-%d %H:%M:%S').strftime('%B %d, %Y')
    for image in images:
        image_names.append(image.name)
    print(image_names)
    return render_template('images.html', nickname=current_user.nickname, image_names=images, site=domain, datepicked=dates, date=picked_date)


@app.route('/display/<filename>')
def send_image(filename):
    return send_from_directory(filename)

@app.route('/return-files/')
def return_file():
    filepath =request.args.get('filepath')
    filename =request.args.get('filename')
    return send_file( filepath, attachment_filename=filename, as_attachment=True)


@app.route('/addsite', methods=['GET', 'POST'])
def add_site():
    form = AddSiteForm()
    if form.validate_on_submit():
        # check if the site exists in the DB
        site = Site.query.filter_by(domain=form.domain_name.data).first()
        # if the site does not exist in the db
        new_site = Site(domain=form.domain_name.data,
                        capture_rate=form.rate.data,
                        mobile_capture=form.mobile.data,
                        article_page_capture=form.article.data,
                        date_added=datetime.datetime.now())
        # Add the site to the DB
        db.session.add(new_site)
        #Add the new site to the current users team
        user_team = Team.query.filter(Team.id==current_user.team).first()
        user_team.subscriptions.append(new_site)
        # sites = Site.query.join(Team.subscriptions).filter(Team.id == current_user.team).all()
        #sites.append(new_site)
        db.session.commit()
        return redirect(url_for('get_sites'))

    return render_template('addsite.html', form=form, title='Add site')


@app.route('/create_collection', methods=['GET', 'POST'])
def create_collection():
    form = CreateCollectionForm()
    image = request.args.get('image')
    print(image)
    image_to_add = Image.query.filter_by(id=image).first()
    print(image_to_add)
    if form.validate_on_submit():
        new_collection = Collection(name=form.name.data)
        new_collection._users.append(current_user)
        db.session.add(new_collection)
        if image_to_add is not None:
            collection = Collection.query.filter_by(id=new_collection.id).first()
            collection.images.append(image_to_add)
            print(collection.images)
            db.session.add(new_collection)
        db.session.commit()

        return redirect(url_for('get_user_collections'))


    return render_template('CreateCollection.html', form=form, title='Add collection', image=image)

@app.route('/collections')
def get_user_collections():
    collections = Collection.query.filter(Collection._users.any(id=current_user.id)).all()
    return render_template('collections.html', collections=collections)


@app.route('/collection')
def get_collection_images():
    collection = request.args.get('collection')
    collection_images = Image.query.join(Collection.images).filter(Collection.id == collection).all()
    col_query = Collection.query.filter_by(id=collection).first()
    name = col_query.name
    return render_template('collection_images.html', nickname=current_user.nickname, image_names=collection_images, collection=collection, name=name)


@app.route('/pickcollection')
def select_collection():
    selected_image = request.args.get('image')
    users_collections = Collection.query.filter(Collection._users.any(id=current_user.id)).all()
    return render_template('add_to_collection.html', image=selected_image, collections=users_collections)



@app.route('/add_to_collection', methods=['GET', 'POST'])
def add_to_collection():
    selected_image = request.args.get('image')
    selected_collection = request.args.get('collection')
    image_to_add = Image.query.filter_by(id=selected_image).first()
    chosen_collection = Collection.query.filter_by(id=selected_collection).first()
    chosen_collection.images.append(image_to_add)
    db.session.add(chosen_collection)
    db.session.commit()
    return redirect(url_for('get_user_collections'))


@app.route('/remove_from_collection', methods=['GET', 'POST'])
def remove_image():
    selected_image = request.args.get('image')
    selected_collection = request.args.get('collection')
    image_to_remove = Image.query.filter_by(id=selected_image).first()
    chosen_collection = Collection.query.filter_by(id=selected_collection).first()
    chosen_collection.images.remove(image_to_remove)
    db.session.commit()
    print(chosen_collection.id)
    print(image_to_remove.id)
    return redirect(url_for('get_user_collections'))

@app.route('/team', methods=['GET', 'POST'])
def team():
    user_team = Team.query.filter(Team.id==current_user.team).first()
    team_name = user_team.name
    users = User.query.filter(User.team == user_team.id).all()
    sites = Site.query.join(Team.subscriptions).filter(Team.id == current_user.team).all()
    return render_template('team.html', team=team_name, users=users, sites=sites)



@app.route('/sendcollection', methods=['GET', 'POST'])
def send_collection():
    if request.method =='GET':
        return '<form action="/sendcollection" method= "POST"><input name="email"><input type="submit"></form>'
    email = request.form['email']
    # TODO Check if the user exist in the DB
    # TODO if user exists add to users collections and notify
    # TODO if user does not exist - Allow to download and invite to sign up
    x=1 # to test sending each
    if x == 1:  # Simultate user exists
        # TODO add collection to user
        msg = Message('Confirm Email', sender='e.eddieflores@gmail.com', recipients=[email])
        the_link = url_for('get_dates', _external=True, site='google.com')
        msg.html = render_template('/email-confirmation.html', link=the_link)
        mail.send(msg)
        return "an email confirmation link has been sent to {}".format(request.form['email'])
    else:
        # TODO invite user to join and download images
        return 'yay'



    # TODO