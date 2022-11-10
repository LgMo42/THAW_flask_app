## Main code for the public API using Flask

# link for setting up initial version
## https://www.youtube.com/watch?v=2e4STDACVA8&list=PLCC34OHNcOtqJBOLjXTd5xC0e-VD3siPn
## https://www.youtube.com/watch?v=Rxp3mkg2mRQ&list=PLCC34OHNcOtqJBOLjXTd5xC0e-VD3siPn&index=4


from flask import Flask, jsonify, request, render_template, current_app, g, redirect, url_for, flash
import pymongo
import datetime
import random
import string
from tabulate import tabulate
from decouple import config
import pandas as pd
import gunicorn
from flask_login import UserMixin, login_user, LoginManager, login_required, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField
from wtforms.validators import InputRequired, Length, ValidationError, EqualTo, Length
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)

# list of store for redirecting them to wallet info page with additional features
stores = ['Papdale']

# need a secret key to prevent #CSRF
app.config['SECRET_KEY'] =  config('SECRET_KEY')

# create the login manager to manage user sessions
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'home'


#################################
### Connect to the collections ###
#################################

# use HEROKU Config Vars to get MongoDB Atlas links
# for users DB
host = config('DB_IEP')
# for system db
trans = config('DATA')

# connect to users database using pymongo
thawdb = pymongo.MongoClient(host)
# connect to the user,email,password collection
iep = thawdb.THAWdb.iep

# use HEROKU Config Vars to access the MongoDB Atlas collections
Mondb = pymongo.MongoClient(trans)
# connect to the wallet collection
wall = Mondb.THAW.wallet
# connect to the transaction collection 
trans = Mondb.THAW.transactions


#############################
### create the User Class ###
#############################

# using pymongo to set up the User classe needed for the loggin_manager function
# from https://stackoverflow.com/questions/54992412/flask-login-usermixin-class-with-a-mongodb
class User:
    def __init__(self, username):
        self.username = username

    @staticmethod
    def is_authenticated():
        return True

    @staticmethod
    def is_active():
        return True

    @staticmethod
    def is_anonymous():
        return False

    def get_id(self):
        return self.username

    @staticmethod
    def check_password(password_hash, password):
        return check_password_hash(password_hash, password)


    @login_manager.user_loader
    def load_user(username):
        u = iep.find_one({"username": username})
        if not u:
            return None
        return User(username=u['username'])
    

##############################
### create the Flask Forms ###
##############################

# create the flask form for the registration page
class RegisterForm(FlaskForm):
    # get user ID from client wich must be their THAW URN
    username = StringField("Username", validators=[InputRequired(), Length(min=2, max=20)], render_kw={"placeholder": "THAW ID"})
    email = StringField("Email", validators=[InputRequired(), Length(min=5, max=20)], render_kw={"placeholder": "e.g. me@me.com"})
    # set password length less than passowr field to allow for hashing 
    password = PasswordField("Passsword", validators=[InputRequired(), EqualTo('password2', message='Passwords must match!'), Length(min=4, max=20)], render_kw={"placeholder": "Password"})
    password2 = PasswordField("Confirm Password", validators=[InputRequired(), Length(min=4, max=20)], render_kw={"placeholder": "Re-type Password"})
    submit = SubmitField('Register')

# create the flask form for the login page
class LoginForm(FlaskForm):
    username = StringField(validators=[InputRequired(), Length(min=2, max=20)], render_kw={"placeholder": "Username"})
    password = PasswordField(validators=[InputRequired(), Length(min=2, max=20)], render_kw={"placeholder": "Password"})
    submit = SubmitField('Login')



#######################################
### create the routes for each page ###
#######################################

# home page
@app.route("/", methods=['GET','POST'])
def home():
    form = LoginForm()
    if form.validate_on_submit():
        if iep.count_documents({'username' : form.username.data}) > 0:
            docCur = iep.find({'username' : form.username.data})
            doc = list(docCur)
            user = doc[0]['username']
            password = doc[0]['password']
            if check_password_hash(password, form.password.data):
                loginuser = User(user)
                login_user(loginuser)#, remember=form.data.remember)
                if user in stores:
                    return redirect(url_for('storewalletinfo'))
                else:
                    return redirect(url_for('walletinfo'))
            else:
                loginError = "Password was incorrect"
                return render_template("thawindex.html", form=form, error_statement=loginError) 
        else:
            loginError2 = "Username does not exist"
            return render_template("thawindex.html", form=form, error_statement=loginError2) 
    # set title that will appear in tab at top of page
    title = 'Welcome to THAW'
# return the page using assigned title
    return render_template("thawindex.html", title=title, form=form) 

# logout 
@app.route('/logout', methods=['GET', 'POST'])
@login_required
def logout():
     logout_user()
     return redirect(url_for('home'))


# registration page
@app.route("/register", methods=['GET','POST'])
def register():
    form = RegisterForm()
    if request.method == 'POST':
        if form.validate():
            if iep.count_documents({"username" : form.username.data}) > 0:
                accExist = "User already has an account"
                return render_template("register.html", form=form, error_statement=accExist)
            #elif wall.count_documents({"username" : form.username.data}) > 0:
            elif wall.count_documents({"Username" : form.username.data}) < 1:
                noUser = "Username does not exist"
                return render_template("register.html", form=form, error_statement=noUser)
            else:
                hashpass = generate_password_hash(form.password.data)
                iep.insert_one({'username':form.username.data, 'email':form.email.data, 'password':hashpass})
            return redirect(url_for('home'))
# set title that will appear in tab at top of page
    title = 'Registraion'
# return the page using assigned title
    return render_template("register.html", title=title, form=form) 


# display client wallet info
@app.route("/walletinfo",  methods=['GET','POST'])
@login_required
def walletinfo():
    # get the username    
    username = current_user.username
# if no code entered then redirect to store page with error message  
    if not username:
        error_statement5 = "Username has not been entered"
        return render_template("thawindex.html", error_statement=error_statement5)
# if username is not valid then redirect to home page with error message          
    if wall.count_documents({"Username" : username}) < 1:  
        error_statement6 = "Username is not valid"
        return render_template("thawindex.html", error_statement=error_statement6)
# get document with relating to code from database        
    if wall.count_documents({"Username" : username}) > 0:
        if username in stores:
            return redirect(url_for('storewalletinfo'))
        else:
            wallCurs = wall.find({"Username" : username}, {'_id':0,})
            docs = list(wallCurs)
            URN = docs[0]['URN']
            food = docs[0]['Food']
            elec = docs[0]['Electricity']
            cash = docs[0]['Cash']
            # create a df to make a table of received transactions
            if trans.count_documents({"Recipient" : URN}) > 0:
                tranCur = trans.find({"Recipient" : URN}, {'_id':0,})
                alltrans = list(tranCur)
                df = pd.DataFrame(alltrans)
                if "Comments" not in df:
                    df['Comments'] = 'None'
                if "Postcode" not in df:
                    df['Postcode'] = 'None'
                if "Transaction Type" not in df:
                    df['Transaction Type'] = 'None'
                df = df.drop(['Postcode', 'Sender', 'Recipient', 'Comments', 'Type of Value', 'Delivery Method', 'Transaction Type'], axis=1)
                df = df.set_index('Date')
                df = df[pd.datetime.today() - pd.offsets.Day(7):].sort_values(['Date', 'Time'], ascending=[False,False])
            else:
                df = df = pd.DataFrame(index=range(1))
    title = 'Wallet'
    return render_template("walletinfo.html", title=title, username=username, URN=URN, food=food, elec=elec, cash=cash, tables=[df.to_html(classes='data', justify='center', col_space='100px', na_rep='Unused', index=True)], titles=df.columns.values)

# display store wallet info with additional features to be added
@app.route("/storewalletinfo",  methods=['GET','POST'])
@login_required
def storewalletinfo():
    # get the username from previous page    
    username = current_user.username
# if no code entered then redirect to store page with error message  
    if not username:
        error_statement5 = "Username has not been entered"
        return render_template("thawindex.html", error_statement=error_statement5)
    if username not in stores:
            return redirect(url_for('walletinfo'))
# if code is not valid then redirect to home page with error message          
    if wall.count_documents({"Username" : username}) < 1:  
        error_statement6 = "Username is not valid"
        return render_template("thawindex.html", error_statement=error_statement6)
# get document with relating to code from database        
    if wall.count_documents({"Username" : username}) > 0:
        wallCurs = wall.find({"Username" : username}, {'_id':0,})
        docs = list(wallCurs)
        URN = docs[0]['URN']
        food = docs[0]['Food']
        elec = docs[0]['Electricity']
        cash = docs[0]['Cash']
        # create a df to make a table of received transactions
        if trans.count_documents({"Recipient" : URN}) > 0:
            tranCur = trans.find({"Recipient" : URN}, {'_id':0,})
            alltrans = list(tranCur)
            df = pd.DataFrame(alltrans)
            if "Comments" not in df:
                df['Comments'] = 'None'
            if "Postcode" not in df:
                df['Postcode'] = 'None'
            if "Type of Value" not in df:
                df['Type of Value'] = 'None'
            if "Delivery Method" not in df:
                df['Delivery Method'] = 'None'
            df = df.drop(['Postcode', 'Sender', 'Recipient', 'Comments', 'Type of Value', 'Delivery Method', 'Transaction Type'], axis=1)
            df = df.set_index('Date')
            df = df[pd.datetime.today() - pd.offsets.Day(7):].sort_values(['Date', 'Time'], ascending=[False,False])
        else:
            df = df = pd.DataFrame(index=range(1))
    title = 'Store Wallet'
    return render_template("storewalletinfo.html", title=title, username=username, URN=URN, food=food, elec=elec, cash=cash, tables=[df.to_html(classes='data', justify='center', col_space='100px', na_rep='Unused', index=True)], titles=df.columns.values)


# page to check the code if ok and allow client to process transaction
@app.route('/pay', methods=['GET','POST'])
@login_required
def pay():
    # get the username    
    username = current_user.username
    if username in stores:
        return redirect(url_for('refund'))
    else:
        # get the info from previous page    
        URN = request.form.get("URN")
        food = request.form.get("food")
        elec = request.form.get("elec")
        cash = request.form.get("cash")
    # assign date and time for transaction records
        today = datetime.date.today()
        now = datetime.datetime.today().strftime(format = '%H:%M')
    # create a random 16 digit alphanumeric code for store transaction
        Rcode = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
        title = 'Check Details'
        return render_template("pay.html",  title = title, Rcode=Rcode, sender=URN, food=food, elec=elec, cash=cash, today=today, now=now)

# page to check the code if ok and allow store to process transaction
@app.route('/refund', methods=['GET','POST'])
@login_required
def refund():
    # get the username    
    username = current_user.username
    if username not in stores:
        return redirect(url_for('pay'))
    else:
        # get the info from previous page    
        URN = request.form.get("URN")
        food = request.form.get("food")
        elec = request.form.get("elec")
        cash = request.form.get("cash")
    # assign date and time for transaction records
        today = datetime.date.today()
        now = datetime.datetime.today().strftime(format = '%H:%M')
    # create a random 16 digit alphanumeric code for store transaction
        Rcode = ''.join(random.choices(string.ascii_letters + string.digits, k=16))
        title = 'Check Details'
        return render_template("refund.html",  title = title, Rcode=Rcode, sender=URN, food=food, elec=elec, cash=cash, today=today, now=now)


# page to show transaction was completed i.e. new document inserted in to database
@app.route('/accepted', methods=['GET','POST'])
@login_required
def accepted():
    title = 'Accepted'
# get info from previous page    
    recipient = request.form.get("recipient")
    sender = request.form.get('sender')
    Ncode = request.form.get('Rcode'), 
    value = request.form.get('value'), 
    type = request.form.get('type')
    # valueType = request.form.get('valueType'), # removed for now as only one value type being used
    date = request.form.get('date'), 
    comments = request.form.get('comments'),
    food = request.form.get("food")
    elec = request.form.get("elec")
    cash = request.form.get("cash")
    today = datetime.date.today()
    now = datetime.datetime.today().strftime(format = '%H:%M')
    storeBal = wall.find_one({"URN": recipient})[type]
    cliBal =  wall.find_one({"URN": sender})[type]
# if statments to assign postcode for store client used
    if recipient == 'Papdale':
        postcode = 'KW15 1XA'
    elif recipient == 'RGU':
        postcode = 'AB10 7QB'
# create the new document  # datetime.datetime.strptime(date, "%Y-%m-%d")
    newDoc = {'Date': datetime.datetime.strptime(date[0], "%Y-%m-%d"), 'Time': now , 'Sender': sender, 'Type': type, 'Recipient': recipient, 'Value': value[0],  
'Type of Value' :'GBP', 'Transaction Code': Ncode[0],  'Transaction Type': 'Remove',
'Delivery Method': 'App',  'Postcode': postcode,} #, 'Type of Value' : valueType[0]} #removed for now
    # Only process if there are enough funds available for the type selected
    if type == 'Food':
        if int(value[0]) > int(food):
            error_statement = "You do not have enought funds select a lower amount"
            return render_template("pay.html", error_statement=error_statement, Rcode=Ncode[0], sender=sender, today=today, food=food, elec=elec, cash=cash)
    if type == 'Electricity':
        if int(value[0]) > int(elec):
            error_statement = "You do not have enought funds select a lower amount"
            return render_template("pay.html", error_statement=error_statement, Rcode=Ncode[0], sender=sender, today=today, food=food, elec=elec, cash=cash)
    if type == 'Cash':
        if int(value[0]) > int(cash):
            error_statement = "You do not have enought funds select a lower amount"
            return render_template("pay.html", error_statement=error_statement, Rcode=Ncode[0], sender=sender, today=today, food=food, elec=elec, cash=cash) 
    # insert the new document into the transactions collection
    trans.insert_one(newDoc)
    # update the client and Papdale wallet
    wall.update_one({'URN': sender}, {'$set':{type: cliBal - int(value[0])}})
    wall.update_one({'URN': recipient}, {'$set':{type: storeBal + int(value[0])}})
    return render_template("accepted.html",  title = title, recipient=recipient, sender=sender, Ncode=Ncode[0], value=value[0], type=type, date=date[0], postcode=postcode, newDoc=newDoc, food=food, elec=elec, cash=cash, storeBal=storeBal, cliBal=cliBal, URN=sender)

# page to show refund was completed i.e. new document inserted in to database
@app.route('/refunded', methods=['GET','POST'])
@login_required
def refunded():
    title = 'Refunded'
# get info from previous page    
    refundee = request.form.get("refundee")
    sender = request.form.get('sender')
    Ncode = request.form.get('Rcode'), 
    value = request.form.get('value'), 
    type = request.form.get('type')
    # valueType = request.form.get('valueType'), # removed for now as only one value type being used
    date = request.form.get('date'), 
    comments = request.form.get('comments'),
    food = request.form.get("food")
    elec = request.form.get("elec")
    cash = request.form.get("cash")
    today = datetime.date.today()
    now = datetime.datetime.today().strftime(format = '%H:%M')
        # if username is not valid then redirect to refund page with error message          
    if wall.count_documents({"Username" : refundee}) < 1:  
        error_statement = "Username is not valid"
        return render_template("refund.html", error_statement=error_statement, Rcode=Ncode[0], sender=sender, today=today, food=food, elec=elec, cash=cash)
    else:
        wallCurs = wall.find({"Username" : refundee}, {'_id':0,})
        docs = list(wallCurs)
        recipient = docs[0]['URN']
        storeBal = wall.find_one({"URN": recipient})[type]
        cliBal =  wall.find_one({"URN": sender})[type]
# create the new document  # datetime.datetime.strptime(date, "%Y-%m-%d")
    newDoc = {'Date': datetime.datetime.strptime(date[0], "%Y-%m-%d"), 'Time': now , 'Sender': sender, 'Type': type, 'Recipient': recipient, 'Value': value[0],  'Transaction Code': Ncode[0], 'Comments': comments, 'Transaction Type': 'Refund'} #, 'Type of Value' : valueType[0]} #removed for now
    # Only process if there are enough funds available for the type selected
    if type == 'Food':
        if int(value[0]) > int(food):
            error_statement = "You do not have enought funds select a lower amount"
            return render_template("refund.html", error_statement=error_statement, Rcode=Ncode[0], sender=sender, today=today, food=food, elec=elec, cash=cash)
    if type == 'Electricity':
        if int(value[0]) > int(elec):
            error_statement = "You do not have enought funds select a lower amount"
            return render_template("refund.html", error_statement=error_statement, Rcode=Ncode[0], sender=sender, today=today, food=food, elec=elec, cash=cash)
    if type == 'Cash':
        if int(value[0]) > int(cash):
            error_statement = "You do not have enought funds select a lower amount"
            return render_template("refund.html", error_statement=error_statement, Rcode=Ncode[0], sender=sender, today=today, food=food, elec=elec, cash=cash)
    # insert the new document into the transactions collection
    trans.insert_one(newDoc)
    # update the client and Papdale wallet
    wall.update_one({'URN': sender}, {'$set':{type: cliBal - int(value[0])}})
    wall.update_one({'URN': recipient}, {'$set':{type: storeBal + int(value[0])}})
    return render_template("accepted.html",  title = title, recipient=recipient, sender=sender, Ncode=Ncode[0], value=value[0], type=type, date=date[0], newDoc=newDoc, food=food, elec=elec, cash=cash, storeBal=storeBal, cliBal=cliBal, URN=sender, comments=comments, refundee=refundee)

    
# display sent transactions as a table for clients
@app.route("/sent",  methods=['GET','POST'])
@login_required
def sent():
    # get the username and URN
    username = current_user.username
    if username in stores:
        return redirect(url_for('refundssent'))
    else:
        wallCurs = wall.find({"Username" : username}, {'_id':0,})
        docs = list(wallCurs)
        URN = docs[0]['URN']
    # get document with relating to code from database        
        # find the documents where user is the Sender
        if trans.count_documents({"Sender" : URN}) > 0:
            tranCur = trans.find({"Sender" : URN}, {'_id':0,})
            # convert cursor object to list
            alltrans = list(tranCur)
            #convert list to df
            dfs = pd.DataFrame(alltrans)
            # some colums are missing from some (not all) docs so add to remove as if not there the code breaks
            if "Comments" not in dfs:
                dfs['Comments'] = 'None'
            if "Postcode" not in dfs:
                dfs['Postcode'] = 'None'
            if "Type of Value" not in dfs:
                dfs['Type of Value'] = 'None'
            if "Delivery Method" not in dfs:
                dfs['Delivery Method'] = 'None'
            # remove columns do not want user to see
            dfs = dfs.drop(['Postcode', 'Sender', 'Type of Value', 'Delivery Method', 'Transaction Type'], axis=1)
            # set the indext to date so can slice df
            dfs = dfs.set_index('Date')
            # slice the last 21 days from df
            dfs = dfs[pd.datetime.today() - pd.offsets.Day(21):].sort_values(['Date', 'Time'], ascending=[False,False])
        else:
            sentError = "Nothing has been sent"
            food = docs[0]['Food']
            elec = docs[0]['Electricity']
            cash = docs[0]['Cash']
            # create a df to make a table of received transactions
            tranCur = trans.find({"Recipient" : URN}, {'_id':0,})
            alltrans = list(tranCur)
            df = pd.DataFrame(alltrans)
            if "Comments" not in df:
                df['Comments'] = 'None'
            if "Postcode" not in df:
                df['Postcode'] = 'None'
            df = df.drop(['Postcode', 'Sender', 'Recipient', 'Comments', 'Type of Value', 'Delivery Method', 'Transaction Type'], axis=1)
            df = df.set_index('Date')
            df = df[pd.datetime.today() - pd.offsets.Day(7):].sort_values(['Date', 'Time'], ascending=[False,False])
            return render_template("walletinfo.html", username=username, error_statement=sentError, URN=URN, food=food, elec=elec, cash=cash, tables=[df.to_html(classes='data', justify='center', col_space='100px', na_rep='Unused', index=True)], titles=df.columns.values)
    title = 'Transactions Sent'
    return render_template("sent.html", title=title, URN=URN, tables=[dfs.to_html(classes='data', justify='center', col_space='100px', na_rep='Unused', index=True)], titles=dfs.columns.values)


    
# display sent transactions as a table
@app.route("/refundssent",  methods=['GET','POST'])
@login_required
def refundssent():
    # get the username and URN
    username = current_user.username
    if username not in stores:
        return redirect(url_for('sent'))
    else:
        wallCurs = wall.find({"Username" : username}, {'_id':0,})
        docs = list(wallCurs)
        URN = docs[0]['URN']
    # get document with relating to code from database        
        # find the documents where user is the Sender
        if trans.count_documents({"Sender" : URN}) > 0:
            tranCur = trans.find({"Sender" : URN}, {'_id':0,})
            # convert cursor object to list
            alltrans = list(tranCur)
            #convert list to df
            dfs = pd.DataFrame(alltrans)
            # some colums are missing from some (not all) docs so add to remove as if not there the code breaks
            if "Comments" not in dfs:
                dfs['Comments'] = 'None'
            if "Postcode" not in dfs:
                dfs['Postcode'] = 'None'
            if "Type of Value" not in dfs:
                dfs['Type of Value'] = 'None'
            if "Delivery Method" not in dfs:
                dfs['Delivery Method'] = 'None'
            # remove columns do not want user to see
            dfs = dfs.drop(['Postcode', 'Sender', 'Recipient', 'Type of Value', 'Delivery Method', 'Transaction Type'], axis=1)
            # set the indext to date so can slice df
            dfs = dfs.set_index('Date')
            # slice the last 21 days from df
            dfs = dfs[pd.datetime.today() - pd.offsets.Day(21):].sort_values(['Date', 'Time'], ascending=[False,False])
        else:
            sentError = "Nothing has been sent"
            food = docs[0]['Food']
            elec = docs[0]['Electricity']
            cash = docs[0]['Cash']
            # create a df to make a table of received transactions
            tranCur = trans.find({"Recipient" : URN}, {'_id':0,})
            alltrans = list(tranCur)
            df = pd.DataFrame(alltrans)
            if "Comments" not in df:
                df['Comments'] = 'None'
            if "Postcode" not in df:
                df['Postcode'] = 'None'
            df = df.drop(['Postcode', 'Sender', 'Recipient', 'Comments', 'Type of Value', 'Delivery Method', 'Transaction Type'], axis=1)
            df = df.set_index('Date')
            df = df[pd.datetime.today() - pd.offsets.Day(7):].sort_values(['Date', 'Time'], ascending=[False,False])
            return render_template("walletinfo.html", username=username, error_statement=sentError, URN=URN, food=food, elec=elec, cash=cash, tables=[df.to_html(classes='data', justify='center', col_space='100px', na_rep='Unused', index=True)], titles=df.columns.values)
    title = 'Refunds Sent'
    return render_template("refundssent.html", title=title, URN=URN, tables=[dfs.to_html(classes='data', justify='center', col_space='100px', na_rep='Unused', index=True)], titles=dfs.columns.values)


    
# display recieved transactions as a table
@app.route("/received",  methods=['GET','POST'])
@login_required
def received():
    # get the username and URN
    username = current_user.username
    wallCurs = wall.find({"Username" : username}, {'_id':0,})
    docs = list(wallCurs)
    URN = docs[0]['URN']
# get document with relating to code from database        
    # get all docs where user is recipient
    if trans.count_documents({"Recipient" : URN}) > 0:
        tranCur = trans.find({"Recipient" : URN}, {'_id':0,})
        # convert cursor object to list
        alltrans = list(tranCur)
        #convert list to df
        dfr = pd.DataFrame(alltrans)
        # Some colums are missing from some (not all) docs so add to remove as if not there the code breaks
        if "Comments" not in dfr:
            dfr['Comments'] = 'None'
        if "Postcode" not in dfr:
            dfr['Postcode'] = 'None'
        if "Transaction Type" not in dfr:
            dfr['Transaction Type'] = 'None'
        # remove columns do not want user to see
        dfr = dfr.drop(['Postcode', 'Sender', 'Recipient', 'Comments', 'Type of Value', 'Delivery Method', 'Transaction Type', 'Comments'], axis=1)
        dfr = dfr.set_index('Date')
        dfr = dfr[pd.datetime.today() - pd.offsets.Day(28):].sort_values(['Date', 'Time'], ascending=[False,False])
    else:
        recError = "Nothing has been received"
        wallCurs = wall.find({"URN" : URN}, {'_id':0,})
        docs = list(wallCurs)
        food = docs[0]['Food']
        elec = docs[0]['Electricity']
        cash = docs[0]['Cash']
        df = df = pd.DataFrame(index=range(1))
        return render_template("walletinfo.html", error_statement=recError, URN=URN, food=food, elec=elec, cash=cash, tables=[df.to_html(classes='data', justify='center', col_space='100px', na_rep='Unused', index=True)], titles=df.columns.values)
    title = 'Transactions Received'
    return render_template("received.html", title=title, URN=URN, tables=[dfr.to_html(classes='data', justify='center', col_space='100px', na_rep='Unused', index=True)], titles=dfr.columns.values)

# reset wallet 
@app.route('/reset', methods=['GET', 'POST'])
@login_required
def reset():
    # get the username for current user
    username = current_user.username
    # use username to get URN
    wallCurs = wall.find({"Username" : username}, {'_id':0,})
    elecBal =  wall.find_one({"Username": username})['Electricity']
    wall.update_one({"Username": username}, {'$set':{'Electricity': elecBal - elecBal}})
    foodBal =  wall.find_one({"Username": username})['Food']
    wall.update_one({"Username": username}, {'$set':{'Food': foodBal - foodBal}})
    cashBal =  wall.find_one({"Username": username})['Cash']
    wall.update_one({"Username": username}, {'$set':{'Cash': cashBal - cashBal}})
    return redirect(url_for('storewalletinfo'))


if __name__ == "__main__":
    app.run()
