import os
import os.path as op

import sqlite3

from flask import Flask, url_for, g, redirect, render_template, request
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.event import listens_for

from wtforms import form, fields, validators
import flask_admin as admin
import flask_login as login

from flask_admin import helpers, expose
from werkzeug.security import generate_password_hash, check_password_hash

from jinja2 import Markup

from flask_admin.form import rules
import flask_admin as admin
from flask_admin import form as form2
from flask_admin.contrib import sqla
from flask_admin.contrib.sqla import ModelView

from flask_admin.base import MenuLink, Admin, BaseView, expose

import grequests
import requests
import numpy as np
from datetime import datetime

#JSON
import json
from flask import request, Response
import ast

# Create application
app = Flask(__name__, static_folder='files')

# Create dummy secrey key so we can use sessions
app.config['SECRET_KEY'] = 'fcBih@f~zD^/UF"=Y5XoVXrLa&7.>W{:L!g87I,xNRk17)Lm$X5{XrR]h(u:MsU'

# Create in-memory database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///drip_db.sqlite'
app.config['SQLALCHEMY_ECHO'] = True
db = SQLAlchemy(app)

# Create directory for file fields to use
file_path = op.join(op.dirname(__file__), 'files')

#Global Variables
router1 = ''
router2 = ''

rf1Volume = 0
rf2Volume = 0
rf3Volume = 0

try:
    os.mkdir(file_path)
except OSError:
    pass

def parse_int(s):
    try:
        res = int(eval(str(s)))
        if type(res) == int:
            return res
    except:
        return

# Setting
def getSetting():
    global router1
    global router2
    global rf1Volume
    global rf2Volume
    global rf3Volume
    try:
        settings = Settings.query.filter_by(set_id=1).first()
        router1 = settings.set_bar_router_ipone
        router2 = settings.set_bar_router_iptwo
        rf1Volume = settings.set_refill_stationone_vol
        rf2Volume = settings.set_refill_stationtwo_vol
        rf3Volume = settings.set_refill_stationthree_vol
    except:
        print('Server unable to fetch data')
        return

# Create user model.
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(100))
    last_name = db.Column(db.String(100))
    login = db.Column(db.String(80), unique=True)
    email = db.Column(db.String(120))
    password = db.Column(db.String(64))

    # Flask-Login integration
    def is_authenticated(self):
        return True

    def is_active(self):
        return True

    def is_anonymous(self):
        return False

    def get_id(self):
        return self.id

    # Required for administrative interface
    def __unicode__(self):
        return self.username


# Define login and registration forms (for flask-login)
class LoginForm(form.Form):
    login = fields.StringField(validators=[validators.required()])
    password = fields.PasswordField(validators=[validators.required()])

    def validate_login(self, field):
        user = self.get_user()

        if user is None:
            raise validators.ValidationError('Invalid user')

        # we're comparing the plaintext pw with the the hash from the db
        if not check_password_hash(user.password, self.password.data):
        # to compare plain text passwords use
        # if user.password != self.password.data:
            raise validators.ValidationError('Invalid password')

    def get_user(self):
        return db.session.query(User).filter_by(login=self.login.data).first()

class RegistrationForm(form.Form):
    login = fields.StringField(validators=[validators.required()])
    email = fields.StringField()
    password = fields.PasswordField(validators=[validators.required()])

    def validate_login(self, field):
        if db.session.query(User).filter_by(login=self.login.data).count() > 0:
            raise validators.ValidationError('Duplicate username')

    #def is_accessible(self):
    #    return login.current_user.is_authenticated

# Initialize flask-login
def init_login():
    login_manager = login.LoginManager()
    login_manager.init_app(app)

    # Create user loader function
    @login_manager.user_loader
    def load_user(user_id):
        return db.session.query(User).get(user_id)


# Create customized model view class
class MyModelView(sqla.ModelView):
    can_create = False
    can_edit = False

    def is_accessible(self):
        return login.current_user.is_authenticated


# Create customized index view class that handles login & registration
class MyAdminIndexView(admin.AdminIndexView):

    @expose('/')
    def index(self):
        if not login.current_user.is_authenticated:
            return redirect(url_for('.login_view'))
        return super(MyAdminIndexView, self).index()

    @expose('/login/', methods=('GET', 'POST'))
    def login_view(self):
        # handle user login
        form = LoginForm(request.form)
        if helpers.validate_form_on_submit(form):
            user = form.get_user()
            login.login_user(user)

        if login.current_user.is_authenticated:
            return redirect(url_for('.index'))
        link = '<p>Don\'t have an account? <a href="' + url_for('.register_view') + '">Click here to register.</a></p>'
        self._template_args['form'] = form
        #self._template_args['link'] = link
        return super(MyAdminIndexView, self).index()

    @expose('/register/', methods=('GET', 'POST'))
    def register_view(self):
        form = RegistrationForm(request.form)
        if helpers.validate_form_on_submit(form):
            user = User()

            form.populate_obj(user)
            # we hash the users password to avoid saving it as plaintext in the db,
            # remove to use plain text:
            user.password = generate_password_hash(form.password.data)

            db.session.add(user)
            db.session.commit()

            login.login_user(user)
            return redirect(url_for('.index'))
        link = '<p>Already have an account? <a href="' + url_for('.login_view') + '">Click here to log in.</a></p>'
        self._template_args['form'] = form
        self._template_args['link'] = link
        return super(MyAdminIndexView, self).index()

    @expose('/logout/')
    def logout_view(self):
        login.logout_user()
        return redirect(url_for('.index'))


# Create category model
class Category(db.Model):
    __tablename__ = 'category'
    cat_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    cat_name = db.Column(db.String(100))
    cat_type = db.Column(db.Integer)
    cat_desc = db.Column(db.String(200))
    cat_datetime = db.Column(db.DateTime)

    def __str__(self):
        return self.cat_desc

    def is_accessible(self):
        return login.current_user.is_authenticated

# Create Productstatus model
class Productstatus(db.Model):
    __tablename__ = 'productstatus'
    prs_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    prs_stat= db.Column(db.String(20))
    def __str__(self):
        return self.prs_stat

    def is_accessible(self):
        return login.current_user.is_authenticated

# Create Volume model
class Volumes(db.Model):
    __tablename__ = 'volume'
    vol_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    vol_amount= db.Column(db.Integer)
    vol_datetime = db.Column(db.DateTime)
    def __str__(self):
        return self.vol_amount

    def is_accessible(self):
        return login.current_user.is_authenticated

# Create Products model
class Products(db.Model):
    __tablename__ = 'product'
    pro_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    pro_prs_id = db.Column(db.Integer, db.ForeignKey('productstatus.prs_id'),nullable=False)
    pro_name = db.Column(db.Unicode(64), nullable=False)
    pro_desc = db.Column(db.String(100))
    pro_logo = db.Column(db.Unicode(128), nullable=False)
    productstatus = db.relationship('Productstatus', backref='product')
    pro_datetime = db.Column(db.DateTime)
    def __str__(self):
        return self.pro_name

    def is_accessible(self):
        return login.current_user.is_authenticated

# Create Mix(Soda) model
class Mixs(db.Model):
    __tablename__ = 'mix'
    mix_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    mix_prs_id = db.Column(db.Integer, db.ForeignKey('productstatus.prs_id'))
    productstatus = db.relationship('Productstatus', backref='mix')
    mix_name = db.Column(db.Unicode(64), nullable=False)
    mix_desc = db.Column(db.String(100))
    mix_logo = db.Column(db.Unicode(128), nullable=False)
    mix_datetime = db.Column(db.DateTime)
    def __str__(self):
        return self.mix_desc

    def is_accessible(self):
        return login.current_user.is_authenticated

# Create Drink Setting model
class Drinksetting(db.Model):
    __tablename__ = 'drinksetting'
    dri_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    dir_pro_id = db.Column(db.Integer, db.ForeignKey('product.pro_id'))
    product = db.relationship('Products', backref='drinksetting')
    dri_ports = db.Column(db.String(200))
    dri_datetime = db.Column(db.DateTime)
    dri_price = db.Column(db.Float)
    dri_logo = db.Column(db.Unicode(128), nullable=False)

    def is_accessible(self):
        return login.current_user.is_authenticated

# Create Mix Setting model
class Mixsetting(db.Model):
    __tablename__ = 'mixsetting'
    mis_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    mis_pro_id = db.Column(db.Integer, db.ForeignKey('product.pro_id'),nullable=False)
    product = db.relationship('Products', backref='mixsetting')
    mis_mix_id = db.Column(db.Integer, db.ForeignKey('mix.mix_id'))
    mixset = db.relationship('Mixs', backref='mixsetting')
    mis_ports = db.Column(db.String(200),nullable=False)
    mis_pins = db.Column(db.String(200),nullable=False)
    mis_datetime = db.Column(db.DateTime)
    mis_price = db.Column(db.Float)
    mis_logo = db.Column(db.Unicode(128), nullable=False)


    def is_accessible(self):
        return login.current_user.is_authenticated

# Create Soda Setting model
class Sodasetting(db.Model):
    __tablename__ = 'sodasetting'
    sod_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sod_mix_id = db.Column(db.Integer, db.ForeignKey('mix.mix_id'))
    mixset = db.relationship('Mixs', backref='sodasetting')
    sod_pins = db.Column(db.String(200),nullable=False)
    sod_datetime = db.Column(db.DateTime)
    sod_price = db.Column(db.Float)
    sod_logo = db.Column(db.Unicode(128), nullable=False)

    def is_accessible(self):
        return login.current_user.is_authenticated

# Create Order Setting model
class Orders(db.Model):
    __tablename__ = 'order'
    ord_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    ord_customer_name = db.Column(db.String(200))
    pro_prs_id = db.Column(db.Integer, db.ForeignKey('productstatus.prs_id'))
    productstatus = db.relationship('Productstatus', backref='order')
    ord_datetime = db.Column(db.DateTime)

    def __str__(self):
       return self.ord_customer_name

    def is_accessible(self):
        return login.current_user.is_authenticated

# Create approval model
class Userapproval(db.Model):
    __tablename__ = 'user_status'
    uss_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    uss_prs_id = db.Column(db.Integer, db.ForeignKey('productstatus.prs_id'))
    usstatus = db.relationship('Productstatus', backref='user_status')
    uss_datetime = db.Column(db.DateTime)

    #def __str__(self):
    #   return self.ustatus

    def is_accessible(self):
        return login.current_user.is_authenticated

# Create Process Setting model
class Processlist(db.Model):
    __tablename__ = 'process'
    prc_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    prc_ord_id = db.Column(db.Integer, db.ForeignKey('order.ord_id'))
    order = db.relationship('Orders', backref='process')
    prc_status = db.Column(db.Integer)
    prc_blob = db.Column(db.String(200))
    prc_req_col = db.Column(db.String(200))
    prc_type = db.Column(db.Integer)
    prc_prs_id = db.Column(db.Integer, db.ForeignKey('productstatus.prs_id'))
    productstatus = db.relationship('Productstatus', backref='process')
    prc_datetime = db.Column(db.DateTime)

    def is_accessible(self):
        return login.current_user.is_authenticated

# Create Order list model
class Orderlists(db.Model):
    __tablename__ = 'order_list'
    orl_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    orl_orl_id = db.Column(db.Integer, db.ForeignKey('order.ord_id'), nullable=False)
    orl_pro_id = db.Column(db.Integer, db.ForeignKey('product.pro_id'))
    orl_mix_id = db.Column(db.Integer, db.ForeignKey('mix.mix_id'))
    order = db.relationship('Orders', backref='order_list')
    product = db.relationship('Products', backref='order_list')
    mix = db.relationship('Mixs', backref='order_list')
    orl_qt = db.Column(db.Integer, nullable=False)
    orl_volume = db.Column(db.Integer)
    orl_group_id = db.Column(db.Integer)
    orl_with_mix = db.Column(db.Integer, nullable=False)
    orl_datetime = db.Column(db.DateTime)

    def is_accessible(self):
        return login.current_user.is_authenticated

# Create Status list model
class Statuslist(db.Model):
    __tablename__ = 'statuslist'
    sta_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sta_prs_id = db.Column(db.Integer, db.ForeignKey('productstatus.prs_id'))
    productstatus = db.relationship('Productstatus', backref='statuslist')
    sta_name = db.Column(db.Unicode(100), nullable=False)
    sta_desc = db.Column(db.String(200))
    sta_datetime = db.Column(db.DateTime)
    def __str__(self):
        return self.pro_name

    def is_accessible(self):
        return login.current_user.is_authenticated


# Create General Setting model
class Settings(db.Model):
    __tablename__ = 'setting'
    set_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    set_bar_router_ipone = db.Column(db.Unicode(50), nullable=False)
    set_bar_router_iptwo = db.Column(db.Unicode(50), nullable=False)
    set_single_shot_volume = db.Column(db.Integer, nullable=False)
    set_double_shot_volume = db.Column(db.Integer, nullable=False)
    set_refill_stationone_vol = db.Column(db.Integer, nullable=False)
    set_refill_stationtwo_vol = db.Column(db.Integer, nullable=False)
    set_refill_stationthree_vol = db.Column(db.Integer, nullable=False)
    set_sodatimer_mix = db.Column(db.Integer, nullable=False)
    set_sodatimer_soda = db.Column(db.Integer, nullable=False)
    set_datetime = db.Column(db.DateTime)

    def is_accessible(self):
        return login.current_user.is_authenticated


class CategoryAdmin(sqla.ModelView):
    column_display_pk = True
    form_columns = ['cat_name', 'cat_type','cat_desc','cat_datetime']

    def is_accessible(self):
        return login.current_user.is_authenticated

class ProductstatusAdmin(sqla.ModelView):
    column_display_pk = True
    form_columns = ['prs_id','prs_stat']   
    column_labels = dict(prs_id='Status Code', prs_stat='Status') 

    def is_accessible(self):
        return login.current_user.is_authenticated

class ProductAdmin(sqla.ModelView):
    #column_display_pk = True
    can_create = False
    can_delete = False
    form_excluded_columns = ('pro_id')
    column_labels = dict(pro_name='Product name',
                         pro_desc='Description', 
                         pro_logo='Logo',
                         productstatus="Status",
                         pro_datetime = "Date updated" )
    form_columns = ['pro_name', 'pro_name','pro_desc','pro_logo','productstatus','pro_datetime']

    def _list_thumbnail(view, context, model, pro_logo):
        if not model.pro_logo:
            return ''

        return Markup('<img src="%s">' % url_for('static',
                                                 filename=form2.thumbgen_filename(model.pro_logo)))

    column_formatters = {
        'pro_logo': _list_thumbnail
    }

    # Alternative way to contribute field is to override it completely.
    # In this case, Flask-Admin won't attempt to merge various parameters for the field.
    form_extra_fields = {
        'pro_logo': form2.ImageUploadField('Product logo',
                                      base_path=file_path,
                                      thumbnail_size=(100, 100, True))
    }

    def is_accessible(self):
        return login.current_user.is_authenticated

class MixtAdmin(sqla.ModelView):
    #column_display_pk = True
    can_create = False
    can_delete = False
    form_excluded_columns = ('mix_id')
    column_labels = dict(mix_name='Product Name', mix_desc='Description', mix_logo='Logo',productstatus="Status", mix_datetime = "Date updated")
    form_columns = ['mix_name', 'mix_name','mix_desc','mix_logo','productstatus','mix_datetime']

    def _list_thumbnail(view, context, model, mix_logo):
        if not model.mix_logo:
            return ''

        return Markup('<img src="%s">' % url_for('static',
                                                 filename=form2.thumbgen_filename(model.mix_logo)))

    column_formatters = {
        'mix_logo': _list_thumbnail
    }

    # Alternative way to contribute field is to override it completely.
    # In this case, Flask-Admin won't attempt to merge various parameters for the field.
    form_extra_fields = {
        'mix_logo': form2.ImageUploadField('Product logo',
                                      base_path=file_path,
                                      thumbnail_size=(100, 100, True))
    }

    def is_accessible(self):
        return login.current_user.is_authenticated

class DrinksettinAdmin(sqla.ModelView):
    #column_display_pk = True
    # can_create = False
    # can_delete = False
    # can_edit = False
    form_excluded_columns = ('dri_id')
    column_labels = dict(product='Booze Name', dri_ports='Router Ports', dri_datetime = "Date updated", dri_price = 'Price', dri_logo = 'Logo')
    # form_columns = ['product','dri_ports', 'dri_datetime']
    column_exclude_list = ('dri_ports')

    def is_accessible(self):
        return login.current_user.is_authenticated

    def _list_thumbnail(view, context, model, dri_logo):
        if not model.dri_logo:
            return ''

        return Markup('<img src="%s">' % url_for('static',
                                                 filename=form2.thumbgen_filename(model.dri_logo)))

    column_formatters = {
        'dri_logo': _list_thumbnail
    }

    # Alternative way to contribute field is to override it completely.
    # In this case, Flask-Admin won't attempt to merge various parameters for the field.
    form_extra_fields = {
        'dri_logo': form2.ImageUploadField('Product logo',
                                      base_path=file_path,
                                      thumbnail_size=(100, 100, True))
    }
    

class MixsettingAdmin(sqla.ModelView):
    #column_display_pk = True
    can_create = False
    #can_delete = False
    #can_edit = False
    form_excluded_columns = ('mis_id','mis_ports','mis_pins')
    column_labels = dict(product='Booze', mixset='Mix Set',mis_ports="Router Ports", mis_pins="Mix Pins",mis_datetime='Datetime of update', mis_price = 'Price', mis_logo = 'Logo')
    # form_columns = ['product','mixset','mis_ports','mis_pins', 'mis_datetime']
    column_exclude_list = ('mis_ports','mis_pins')

    def is_accessible(self):
        return login.current_user.is_authenticated

    def _list_thumbnail(view, context, model, mis_logo):
        if not model.mis_logo:
            return ''

        return Markup('<img src="%s">' % url_for('static',
                                                 filename=form2.thumbgen_filename(model.mis_logo)))

    column_formatters = {
        'mis_logo': _list_thumbnail
    }

    # Alternative way to contribute field is to override it completely.
    # In this case, Flask-Admin won't attempt to merge various parameters for the field.
    form_extra_fields = {
        'mis_logo': form2.ImageUploadField('Product logo',
                                      base_path=file_path,
                                      thumbnail_size=(100, 100, True))
    }

class SodasettingAdmin(sqla.ModelView):
    #column_display_pk = True
    can_create = False
    #can_delete = False
    #can_edit = False
    form_excluded_columns = ('sod_id')
    column_labels = dict(mixset='Soda', sod_pins="Soda Pins",sod_datetime='Datetime of update', sod_price = 'Price', sod_logo = 'Logo')
    # form_columns = ['mixset','sod_pins', 'sod_datetime']
    column_exclude_list = ('sod_pins')

    def is_accessible(self):
        return login.current_user.is_authenticated

    def _list_thumbnail(view, context, model, sod_logo):
        if not model.sod_logo:
            return ''

        return Markup('<img src="%s">' % url_for('static',
                                                 filename=form2.thumbgen_filename(model.sod_logo)))

    column_formatters = {
        'sod_logo': _list_thumbnail
    }

    # Alternative way to contribute field is to override it completely.
    # In this case, Flask-Admin won't attempt to merge various parameters for the field.
    form_extra_fields = {
        'sod_logo': form2.ImageUploadField('Product logo',
                                      base_path=file_path,
                                      thumbnail_size=(100, 100, True))
    }


class OrderAdmin(sqla.ModelView):
    #column_display_pk = True
    form_excluded_columns = ('ord_id')
    column_labels = dict(ord_customer_name='Customer name', productstatus='Status', ord_datetime='Datetime')
    form_columns = ['ord_customer_name','productstatus','ord_datetime']

    def is_accessible(self):
        return login.current_user.is_authenticated

class OrderListAdmin(sqla.ModelView):
    #column_display_pk = True
    form_excluded_columns = ('orl_id')
    column_labels = dict(order='Customer name', 
                        product='Booze', 
                        mix='Mix',
                        orl_volume='Volume',
                        orl_qt='Quantity',
                        orl_with_mix='With Mix 0 = No, 1 =mix , 2 = soda',
                        orl_datetime='Data of update')
    form_columns = ['order','product','mix','orl_volume','orl_qt','orl_with_mix','orl_datetime']

    def is_accessible(self):
        return login.current_user.is_authenticated

class VolumesAdmin(sqla.ModelView):
    #column_display_pk = True
    form_excluded_columns = ('vol_id')
    #column_labels = dict(ord_customer_name='Customer name', productstatus='Status', ord_datetime='Datetime')
    form_columns = ['vol_amount','vol_datetime']

    def is_accessible(self):
        return login.current_user.is_authenticated

class ProcesslistAdmin(sqla.ModelView):
    #column_display_pk = True
    form_excluded_columns = ('prc_id','prc_status')
    form_columns = ['order','prc_blob','prc_type','prc_req_col','productstatus','prc_datetime']
    column_labels = dict(order='Customer name',
                        productstatus='Transaction Status', 
                        prc_blob = 'Process Blob',
                        prc_req_col = 'Stations',
                        prc_type = 'Trasaction type 1 = booze, 2 = mix, 3 = soda',
                        prc_datetime='Datetime')

    sta_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    sta_prs_id = db.Column(db.Integer, db.ForeignKey('productstatus.prs_id'))
    productstatus = db.relationship('Productstatus', backref='statuslist')
    sta_name = db.Column(db.Unicode(100), nullable=False)
    sta_desc = db.Column(db.String(200))
    sta_datetime = db.Column(db.DateTime)

    def is_accessible(self):
        return login.current_user.is_authenticated


class StatuslistAdmin(sqla.ModelView):
    #column_display_pk = True
    can_create = False
    can_delete = False
    form_excluded_columns = ('sta_id')
    form_columns = ['sta_desc','sta_name','productstatus','sta_datetime']
    column_labels = dict(sta_desc='Booze Description',
                    sta_name='Booze Name', 
                    productstatus = 'Status',
                    sta_datetime = 'Datetime of update')
    def is_accessible(self):
        return login.current_user.is_authenticated


class SettingAdmin(sqla.ModelView):
    #column_display_pk = True
    can_create = False
    can_delete = False
    form_excluded_columns = ('set_id')
    column_labels = dict(set_bar_router_ipone="Bartendro router 1 IP", 
                        set_bar_router_iptwo="Bartendro router 2 IP", 
                        set_single_shot_volume="Single shot volume", 
                        set_double_shot_volume="Double shot volume", 
                        set_refill_stationone_vol = "Station 1 Refill Volume",
                        set_refill_stationtwo_vol="Station 2 Refill Volume",
                        set_refill_stationthree_vol="Station 3 Refill Volume",
                        set_sodatimer_mix="Timer for soda mix",
                        set_sodatimer_soda="Timer for soda",                        
                        set_datetime="Date of update")

    form_columns = ['set_bar_router_ipone',
                    'set_bar_router_iptwo',
                    'set_single_shot_volume','set_double_shot_volume',
                    'set_refill_stationone_vol',
                    'set_refill_stationtwo_vol',
                    'set_refill_stationthree_vol',
                    'set_sodatimer_mix',
                    'set_sodatimer_soda',
                    'set_datetime']

    def is_accessible(self):
        return login.current_user.is_authenticated

# Create approval Admin model
class UserapprovalAdmin(sqla.ModelView):
    can_create = False
    can_delete = False
    form_excluded_columns = ('uss_id')
    column_labels = dict(usstatus="Status", uss_datetime = "Date time")
    form_columns = ['usstatus','uss_datetime']
        
    def is_accessible(self):
        return login.current_user.is_authenticated
    
@listens_for(Products, 'after_delete')
def del_product(mapper, connection, target):
    if target.pro_logo:
        # Delete image
        try:
            os.remove(op.join(file_path, target.pro_logo))
        except OSError:
            pass

        # Delete thumbnail
        try:
            os.remove(op.join(file_path,
                              form.thumbgen_filename(target.pro_logo)))
        except OSError:
            pass

# Flask views
@app.route('/')
def index():
    return render_template('index.html')

# Initialize flask-login
init_login()

# Create admin
admin = admin.Admin(app, name='Drip Admin',index_view=MyAdminIndexView(), base_template='my_master.html')
#admin.add_view(CategoryAdmin(Category, db.session))
admin.add_view(ProductAdmin(Products, db.session, 'Booze List'))
admin.add_view(MixtAdmin(Mixs, db.session, 'Mix List'))
admin.add_view(OrderAdmin(Orders,db.session, 'Order'))
admin.add_view(OrderListAdmin(Orderlists,db.session, 'Order List'))
#admin.add_view(VolumesAdmin(Volumes,db.session))
admin.add_view(MixsettingAdmin(Mixsetting, db.session, 'Mix Setting'))
admin.add_view(DrinksettinAdmin(Drinksetting, db.session, 'Booze Setting'))
admin.add_view(SodasettingAdmin(Sodasetting, db.session, 'Soda Setting'))
admin.add_view(ProcesslistAdmin(Processlist,db.session, 'Process List'))
admin.add_view(StatuslistAdmin(Statuslist,db.session, 'Station Status'))
admin.add_view(ProductstatusAdmin(Productstatus, db.session, 'Status Setting'))
admin.add_view(MyModelView(User, db.session))
admin.add_view(SettingAdmin(Settings,db.session, 'General Setting'))
admin.add_view(UserapprovalAdmin(Userapproval,db.session, 'User Status'))

# Add links with categories
#admin.add_link(MenuLink(name='General Setting', category='Settings', url='http://192.168.1.124:5000/admin/settings/'))
#admin.add_link(MenuLink(name='Booze Settng', category='Settings', url='http://192.168.1.124:5000/admin/drinksetting/'))
#admin.add_link(MenuLink(name='Mix Setting', category='Settings', url='http://192.168.1.124:5000/admin/mixsetting/'))

#Test route
@app.route('/api/test')
def test():
    global router1
    global router2

    blob = [router1+'booze75=30&booze63=30&booze70=30&', router2+'booze74=30&booze69=30&']
    ms = (grequests.get(u) for u in blob)
    grequests.map(ms)
    print(blob)

    return router1


#API's 
@app.route('/api/runrefill', methods=['POST'])
def runrefill():
    global router2
    global rf1Volume
    global rf2Volume
    global rf3Volume

    result = 'failed'
    bayphats = request.json['bayphats'].split(',')
    param = ''
    for path in bayphats :
        booze_ref_volume = 0
        if path != '' :
            if path == 'booze66':
                booze_ref_volume = rf1Volume
            if path == 'booze71':
                booze_ref_volume = rf2Volume
            if path == 'booze75':
                booze_ref_volume = rf3Volume 

            param = param + path + "=" +  str(booze_ref_volume) + "&"

    # Generated URL
    full_url = router2 + param

    try:
        r = requests.get(full_url)
        if r == "ok" :
            result = "success"
        else :
            result = "failed"
    except:
        result = "failed"

    return Response(json.dumps(result),  mimetype='application/json')

# Satation Status
@app.route('/api/stationstatus')
def stationstatus():
    result = 0
    emptylist = []
    try:

        runlist = Statuslist.query.filter_by(sta_prs_id=9).all()

        if runlist is not None:
           # print(runlist + "here")
           for x in runlist :
               emptylist.append(x.sta_id)
           result = emptylist
            
        else :
            result = emptylist
    except:
        result = emptylist

    return Response(json.dumps(result),  mimetype='application/json')

# Station Update
@app.route('/api/stationupdate', methods=['POST'])
def stationupdate():
    result = "failed"
    # bay 1,2,3
    bayid = int(request.json['bayid'])
    #action 1 = to reset, 2 = to set out of order
    action = int(request.json['action']) 

    try:
        result = "failed"

        if action == 1 :
            runupdate = Statuslist.query.filter_by(sta_id=bayid).update(dict(sta_prs_id=8))
        else : 
            runupdate = Statuslist.query.filter_by(sta_id=bayid).update(dict(sta_prs_id=9))

        try:
            db.session.commit()
            result = "success"
        except Exception as e:
            db.session.rollback()
            db.session.flush()
            result = "failed"

    except:
        result = "failed"

    return Response(json.dumps(result),  mimetype='application/json')

# Dispenser runner
@app.route('/api/rundispense', methods=['POST'])
def rundispense():
    result = "failed"
    boozelistid = int(request.json['boozelistid'])
    drinktype = int(request.json['drinktype'])

    try:

        if drinktype == 1 or drinktype == 2 :
            boozelist = []
            runlist = Processlist.query.filter_by(prc_id=boozelistid).filter_by(prc_prs_id=1).first()
            blob = ast.literal_eval(runlist.prc_blob)

            #print(blob)
            ms = (grequests.get(u) for u in blob)
            grequests.map(ms)

            runupdate = Processlist.query.filter_by(prc_id=boozelistid).update(dict(prc_prs_id=6))
            try:
                db.session.commit()
                result = "success"
            except Exception as e:
                db.session.rollback()
                db.session.flush()
                result = "failed"
        else :
            runupdate = Processlist.query.filter_by(prc_id=boozelistid).update(dict(prc_prs_id=6))
            try:
                db.session.commit()
                result = "success"
            except Exception as e:
                db.session.rollback()
                db.session.flush()
                result = "failed"            

    except:
        result = "failed"

    return Response(json.dumps(result),  mimetype='application/json')


# Process 
@app.route('/api/processlist')
def processlist():
    result = ''

    try:
        activeorder = Orders.query.filter_by(pro_prs_id=5).first()
        #print('test2')
        if activeorder.ord_id > 0:
            try:
                #print('test')
                setlist = Processlist.query.filter_by(prc_prs_id=1).filter_by(prc_ord_id=activeorder.ord_id).first()
                colList = setlist.prc_req_col.replace('[','')
                colList1 = colList.replace(']','')
                colListFinal = colList1.replace(' ','')
                result = Response(json.dumps(colListFinal + " " + str(setlist.prc_id) + " " + str(setlist.prc_type)),  mimetype='application/json')
            except:
                runupdate = Orders.query.filter_by(ord_id=activeorder.ord_id).update(dict(pro_prs_id=6))

                try:
                    db.session.commit()
                    result = Response(json.dumps(''),  mimetype='application/json')
                except Exception as e:
                    db.session.rollback()
                    db.session.flush()
                    result = Response(json.dumps(''),  mimetype='application/json')

    except:

        result = Response(json.dumps(''),  mimetype='application/json')

    return result
    #return setlist.prc_req_col

# Order checker
@app.route('/api/checkorders')
def checkorders():

    status = Userapproval.query.filter_by(uss_prs_id=11).all()
    print(len(status))

    return str(len(status))

# Order checker
@app.route('/api/setting')
def sodasetting():
    res = []
    setting = Settings.query.filter_by(set_id=1).first()
    res.append(setting.set_bar_router_ipone)
    res.append(setting.set_bar_router_iptwo)
    res.append(str(setting.set_single_shot_volume))
    res.append(str(setting.set_double_shot_volume))
    res.append(str(setting.set_refill_stationone_vol))
    res.append(str(setting.set_refill_stationtwo_vol))
    res.append(str(setting.set_refill_stationthree_vol))
    res.append(str(setting.set_sodatimer_mix))
    res.append(str(setting.set_sodatimer_soda))
    
    result = str(res).replace('[','').replace(']','').replace("'",'').replace('"','')
    
    #return str(res)
    return Response(json.dumps(result),  mimetype='application/json')

# Order Approval
@app.route('/api/approveorder', methods=['POST'])
def approveorder():

    #status = request.data
    stat = request.json['status']
    #stat = json.dumps(status)
    #print(status)
    #print(status.json())

    #order = Orders.query.filter_by(pro_prs_id=1).first()
    #orderid = order.ord_id
    status = Userapproval.query.filter_by(uss_id=1).update(dict(uss_prs_id=stat))

    result = "failed"

    try:
        db.session.commit()
        result = "success"
    except Exception as e:
        db.session.rollback()
        db.session.flush()
        result = "failed"

    return result
    
#API's 
@app.route('/api/process', methods=['POST'])
def process():

    global router1
    global router2

    customerid = int(request.json['customerid'])
    # bartendro ip for none product
    drinkurl1 = router1
    drinkurl2 = router2

    # bartendro ip for mix product
    mixurlx1 = router1
    mixurlx2 = router2

    # constant link
    conurl1 = router1
    conurl2 = router2

    countDrink = 0
    countMix = 0
    incrementalDrinkCounter = 0

    #Products
    drinkList=[]
    urls = []

    # Mix (more that 2 value. same mix)
    mixurls = [] # final output for mix blob
    mixarray = [] # list of ordered mix.

    #mix dispense bay
    mixbay = []
    drinkbay = []
    
    # Mix 
    multimix = []
    sodalistarray = []
    sodax = []
    dimMixCounter = 0

    #date time
    now = datetime.now()

    #change orl_orl_id to variable instead of hardcode value
    orderlist = Orderlists.query.filter_by(orl_orl_id=customerid).all()
    #orderlist = Orderlists.query.order_by(Orderlists.orl_mix_id)
    for o in orderlist:

        #mix dispense bay
        duplimixbay = []
        
        # bartendro ip for mix product
        mixurl1 = router1
        mixurl2 = router2

        pm = 0
        pd = 0
        vol = 0
        qt = 0

        # Mix process
        if o.orl_with_mix == 2 :
            pm = o.orl_mix_id
            vol = o.orl_volume
            qt = o.orl_qt

            ctr = 0

            sodalist = Sodasetting.query.filter_by(sod_mix_id=pm).first()
            getsodaList = sodalist.sod_pins.split(',')

            for g in getsodaList[:qt]:
                currentsoda = g
                #print(currentsoda)
                if any(currentsoda in s for s in sodalistarray):
                    sodax.append(currentsoda)
                    #print(sodax)
                else:
                    sodalistarray = np.append(sodalistarray,str(g))


         # Mix process
        if o.orl_with_mix == 1 :
            pm = o.orl_mix_id
            pd = o.orl_pro_id
            vol = o.orl_volume
            qt = o.orl_qt

            ctr = 0

            #mixList = [] # query
            mixlist = Mixsetting.query.filter_by(mis_mix_id=pm). \
                                       filter_by(mis_pro_id=pd).first()
            getmixList = mixlist.mis_ports.split(',')
                        
            for g in getmixList[:qt]:
                #print(g)
                currentbooze = g
                booze = g[:-2]
                #print(booze)
                ip = parse_int(g[7:-1])
                pos = parse_int(g[8:])

                mixip1 = []
                mixip2 = []

                mixurlsx = []

                if any(currentbooze in s for s in mixarray):

                    ctr = ctr + 1
                    if int(ip) == 1:
                        mixurl1 = mixurl1 + booze + "=" + str(vol) + "&"
                    else:
                        mixurl2 = mixurl2 + booze + "=" + str(vol)  + "&"

                    #print(mixarray)
                    if mixurl1!=conurl1:
                        mixurlsx.append(mixurl1)
                        duplimixbay.append(pos)

                    if mixurl2!=conurl2:
                        mixurlsx.append(mixurl2)
                        duplimixbay.append(pos)

                    if qt == 2 :
                        if ctr == 2:
                            dupm = 0
                            if len(duplimixbay) > 2  :
                                dupm = duplimixbay[:-1]
                            else :
                                dupm = duplimixbay

                            insmix = Processlist(prc_ord_id=customerid,prc_status=1,prc_blob=str(mixurlsx),prc_type=2,prc_req_col=str(dupm),prc_prs_id=1,prc_datetime=now)
                            db.session.add(insmix)
                            db.session.commit()
                            duplimixbay.clear()
                    else :
                        insmix = Processlist(prc_ord_id=customerid,prc_status=1,prc_blob=str(mixurlsx),prc_type=2,prc_req_col=str(duplimixbay),prc_prs_id=1,prc_datetime=now)
                        db.session.add(insmix)
                        db.session.commit()
                        duplimixbay.clear()
                else :
                    if int(ip) == 1:
                        mixip1.append(booze + "=" + str(vol) + str(ip) + str(pos))
                        multimix.append(mixip1)
                        if pos > 0 :
                            mixbay.append(pos)

                    else:
                        mixip2.append(booze + "=" + str(vol)  + str(ip) + str(pos))
                        multimix.append(mixip2)
                        
                        if pos > 0 :
                            mixbay.append(pos)                        
                               
                mixarray = np.append(mixarray,booze+str(ip)+str(pos))

         # Booze process
        if o.orl_with_mix == 0 :
            #print("check if how many time it went here")
            pt = o.orl_pro_id
            vol = str(o.orl_volume)
            qt = o.orl_qt
            portlist = Drinksetting.query.filter_by(dir_pro_id=pt).first()
            getList = portlist.dri_ports.split(',')
            #print(getList)
            for g in getList[incrementalDrinkCounter:incrementalDrinkCounter+qt]:
                gi = incrementalDrinkCounter+qt

                booze = g[:-2]
                ip = parse_int(g[7:-1])
                pos = parse_int(g[8:])
                if int(ip) == 1:
                    drinkurl1 = drinkurl1 + booze + "=" + str(vol) + "&"
                    if pos > 0 :
                        drinkbay.append(pos)
                else:
                    drinkurl2 = drinkurl2 + booze + "=" + str(vol)  + "&"
                    if pos > 0 :
                        drinkbay.append(pos)

            incrementalDrinkCounter = incrementalDrinkCounter + qt

    # mix process
    for x in multimix :
        for y in x :
            ip = y[10:-1]
            booze = y[:-2]
            pos = y[11:]

            if int(ip) == 1:
                mixurlx1 = mixurlx1 + booze + "&"
            else:
                mixurlx2 = mixurlx2 + booze + "&"

    # Soda process
    if len(sodax) > 0:
        sodax = list(map(int, sodax))
        insmix = Processlist(prc_ord_id=customerid,prc_status=1,prc_type=3,prc_req_col=str(sodax),prc_prs_id=1,prc_datetime=now)
        db.session.add(insmix)
        db.session.commit()
        duplimixbay.clear()

    if len(sodalistarray) > 0:
        sodalistarray = list(map(int, sodalistarray))
        insmix = Processlist(prc_ord_id=customerid,prc_status=1,prc_type=3,prc_req_col=str(sodalistarray),prc_prs_id=1,prc_datetime=now)
        db.session.add(insmix)
        db.session.commit()
        duplimixbay.clear()

    # append mix url
    if mixurlx1 != mixurl1 :
        mixurls.append(mixurlx1)
    if mixurlx2 != mixurl2 :
        mixurls.append(mixurlx2)

    #drinks process

    if drinkurl1!=conurl1:
        urls.append(drinkurl1)
    if drinkurl2!=conurl2:
        urls.append(drinkurl2)

    if len(urls) > 0 :
        ins = Processlist(prc_ord_id=customerid,prc_status=1,prc_blob=str(urls),prc_type=1,prc_req_col=str(drinkbay),prc_prs_id=1,prc_datetime=now)
        db.session.add(ins)
        db.session.commit()   

    if len(mixurls) > 0 :
        insmixx = Processlist(prc_ord_id=customerid,prc_status=1,prc_blob=str(mixurls),prc_type=2,prc_req_col=str(mixbay),prc_prs_id=1,prc_datetime=now)
        db.session.add(insmixx)
        db.session.commit()    

    #mix dispense bay
    mixbay.clear()
    drinkbay.clear()

    return "success"

if __name__ == '__main__':
    #Setting
    getSetting()
    # Create DB
    db.create_all()

    # Start app
    app.run(host='192.168.1.124', port=5000, debug=True)