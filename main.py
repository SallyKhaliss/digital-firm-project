from fastapi import FastAPI, Request
import sqlite3
import uvicorn
import requests
from datetime import date

app = FastAPI()

# Init database - Axel
db = sqlite3.connect('database.db', isolation_level=None)

db.execute(
    '''
        CREATE TABLE IF NOT EXISTS companies(
            vat TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            adress TEXT NOT NULL,
            iban TEXT NOT NULL
        )
    '''
)

db.execute(
    '''
        CREATE TABLE IF NOT EXISTS customers(
            iban TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            email TEXT NOT NULL,
            adress TEXT NOT NULL,
            company TEXT NOT NULL
        )
    '''
)

db.execute(
    '''
        CREATE TABLE IF NOT EXISTS quotes(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            company TEXT NOT NULL,
            quantity INT NOT NULL,
            price FLOAT NOT NULL,
            currency TEXT NOT NULL
        )
    '''
)

db.execute(
    '''
        CREATE TABLE IF NOT EXISTS subscriptions(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            customer TEXT NOT NULL,
            quote INT NOT NULL,
            accepted BOOL NOT NULL DEFAULT 0,
            starting TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    '''
)

db.execute(
    '''
        CREATE TABLE IF NOT EXISTS invoices(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            subscription INT NOT NULL,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            paid BOOL NOT NULL,
            received FLOAT NOT NULL DEFAULT 0
        )
    '''
)

db.execute(
    '''
        CREATE TABLE IF NOT EXISTS rates(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            currency TEXT NOT NULL,
            rate FLOAT NOT NULL
        )
    '''
)
# dans le cours ils ferment à chaque fois bien la base de données, à faire aussi ici?

# Helper functions - Axel
# Check credit card validity


def CheckCreditCard(number):
    try:
        last = int(number[-1])
        number = number[:-1][::-1]
        total = last
        for digit in number:
            digit = int(digit)
            if(digit % 2 == 0):
                if(digit*2 <= 9):
                    total += digit*2
                else:
                    total += digit * 2 - 9
        return total % 10 == 0
    except:
        return False

# Conversion between currencies
# - Example
# - Convert 100$ to €:
# - AnyVariableName = convertToEuro(100, "USD")


def convertToEuro(amount, currency):
    today = str(date.today())
    actualRate = db.execute(
        'SELECT * FROM rates WHERE currency = ? AND date = ?', (currency, today)).fetchall()
    rate = 1
    if(len(actualRate) > 0):
        rate = actualRate[0][3]
    else:
        rateFromApi = requests.get(
            'https://v6.exchangerate-api.com/v6/9f3b63e712fb3bf92872a235/latest/'+currency).json()
        if(rateFromApi['result'] == "success"):
            rate = rateFromApi['conversion_rates']['EUR']
            db.execute(
                'INSERT INTO rates (date, currency, rate) VALUES (?,?,?)', (today, currency, rate))
        else:
            rate = 1
    return amount * rate

# # Routes
# # Create company account - Salma
# vat TEXT PRIMARY KEY, # name TEXT NOT NULL, # email TEXT NOT NULL, # adress TEXT NOT NULL, # iban TEXT NOT NULL


@app.post("/create-company-account")
async def root(payload: Request):
    body = await payload.json()

    name = body['name']
    vat = body['VAT']
    email = body['email']
    adress = body['adress']
    iban = body['IBAN']

    db.execute(
        'INSERT INTO companies (vat, name, email, adress, iban) VALUES (?,?,?,?,?)',
        (vat, name, email, adress, iban)
    )

    return {
        "statusCode": 200,
        "message": vat + " company has been saved!"
    }

# # Create customer account - Salma


@app.post("/create-customer-account")
async def root(payload: Request):
    body = await payload.json()

    iban = body['IBAN']
    name = body['name']
    email = body['email']
    adress = body['adress']
    company = body['company']

    db.execute(
        'INSERT INTO customers(iban, name, email, adress, company) VALUES (?,?,?,?,?)',
        (iban, name, email, adress, company)
    )

    return {
        "statusCode": 200,
        "message": name + " customer has been saved!"
    }

# # Create quote - Zelie


@app.post("/create-quote")
async def root(payload: Request):
    body = await payload.json()

    quote = db.execute(
        'INSERT INTO quotes(company, quantity, price, currency) VALUES (?,?,?,?)',
        (body['company'], body['quantity'], body['price'], body['currency'])
    )

    print(quote)

    return {
        "statusCode": 200,
        "message": "Quote (id: " + str(quote.lastrowid) + ") has been saved!"
    }


# # Create subscription - Zélie
@app.post("/create-subscription")
async def root(payload: Request):
    body = await payload.json()

    subscription = db.execute(
        'INSERT INTO subscriptions (customer, quote, accepted) VALUES (?,?,0)',
        (body['customer'], body['quote'])
    )

    return {
        "statusCode": 200,
        "message": "Subscription (id: " + str(subscription.lastrowid) + ") has been saved for customer " + body['customer'] + "!"
    }

# # Update subscription - Victor


@app.post("/update-subscription")
async def root(payload: Request):
    body = await payload.json()

    subscription = int(body['subscription'])

    if body['status'] == "accepted":

        # We set the subscription as accepted
        db.execute(
            'UPDATE subscriptions SET accepted = 1 WHERE id = ?',
            ([subscription])
        )

        # We create the first invoice for the subscription
        db.execute(
            'INSERT INTO invoices (subscription, paid) VALUES (?,0)',
            ([subscription])
        )

        return {
            "statusCode": 200,
            "message": "Subscription (id: " + str(subscription) + ") has been accepted!"
        }
    else:
        return {
            "statusCode": 400,
            "message": "Bad request."
        }


# # Retrieve pending invoices - Victor
@app.post("/pending-invoices")
async def root(payload: Request):
    body = await payload.json()

    customer_subscriptions = db.execute(
        'SELECT * FROM subscriptions WHERE customer = ?',
        ([body['customer']])
    ).fetchall()

    invoices = []
    for subscription in customer_subscriptions:
        pending_invoices = db.execute(
            'SELECT * FROM invoices WHERE paid=0 AND subscription = ?',
            (str(subscription[0]))
        ).fetchall()

        if(len(pending_invoices) > 0):
            invoices.append(pending_invoices)

    return {
        "statusCode": 200,
        "message": "The following invoices are still waiting to be paid: ",
        "invoices": invoices
    }


# # Update invoice (paid/unpaid) - Tom
@app.post("/update-invoice")
async def root(payload: Request):
    body = await payload.json()

    id = body['invoice']
    received = body['received']
    number = body['card']

    invoice = db.execute(
        'SELECT * FROM invoices WHERE id = ?',
        (int(id),)
    ).fetchall()

    # invoice[0] = Invoice to be updated
    # invoice[0][4] = Fouth column of invoice to be updated: 'received'

    if (len(invoice) > 0):
        if CheckCreditCard(number) == True:
            if (received < invoice[0][3] - invoice[0][4]) == 0:

                if (received + invoice[0][4] == invoice[0][3]):
                    db.execute(
                        'UPDATE invoices SET paid = 1, received = ? WHERE id = ?',
                        (float(received), int(id))
                    )
                else:
                    db.execute(
                        'UPDATE invoices SET received = ? WHERE id = (?)',
                        (float(received), int(id))
                    )

                return {
                    "statusCode": 200,
                    "message": "Invoice successfully updated!"
                }
            else:
                return {
                    "statusCode": 400,
                    "message": "Total received amount can't exceed invoice amount."
                }
        else:
            return {
                "statusCode": 400,
                "message": "Invalid credit card."
            }
    else:
            return {
                "statusCode": 400,
                "message": "Invalid invoice."
            }


# # Retrieve company's statistics - Tom
@ app.post("/company-statistics")
async def root(payload: Request):
    body=await payload.json()

    id=body['company']

    MRR=0

    quotes=db.execute(
        'SELECT * FROM quotes WHERE company = ?',
        (str(id),)
    ).fetchall()

    print("Quotes: " + str(len(quotes)))

    subscriptions_counter=0

    for quote in quotes:
        price=convertToEuro(quote[3], quote[4])

        subscriptions=db.execute(
            'SELECT * FROM subscriptions WHERE quote = ? AND accepted = 1',
            (quote[0],)
        ).fetchall()

        print('Subscriptions:' + str(len(subscriptions)))

        subscriptions_counter += len(subscriptions)

        # MRR = Number of subscriptions for the quote * price of the quote
        MRR += len(subscriptions) * price

    return {
        "MRR": MRR,
        "ARR": 12 * MRR,
        "ARC": (MRR / subscriptions_counter) if subscriptions_counter > 0 else "Undefined."
    }

# # Start server
if __name__ == '__main__':
    uvicorn.run(app, host='127.0.0.1', port=8000)
