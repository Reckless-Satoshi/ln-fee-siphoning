import os
import sys
import json
from subprocess import PIPE, Popen
import subprocess
import time
import requests

LNMToken = 'Your_LNMarkets_JWT_Token'

iterations = 1          #Number of deposit/withdrawal cycles
amount_sats = 999000    #Sats to deposit/withdraw in each cycle
use_tor = False         #If true, makes requests behind TOR

'''
In LNMArkets it was possible to deposit 1 million sat, and withdraw it
collecting up to 10 000 ppm (1%) as routing fees in the routing node.

'''

def get_tor_session():
    session = requests.session()
    session.proxies = {'http':  'socks5://127.0.0.1:9050',
                       'https': 'socks5://127.0.0.1:9050'}
    return session



#Generate remote invoice
def gen_remote_invoice():

    url = "https://api.lnmarkets.com/v1/user/deposit"

    payload = {
        "amount": amount_sats,
        "unit": "sat"
    }
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": "Bearer " + LNMToken
    }

    if use_tor:
        response = session.request("POST", url, json=payload, headers=headers)
    else:
        response = requests.request("POST", url, json=payload, headers=headers)

    if is_error(response.text):
        # uncomment for debugging
        # print(response.text)
        return 'NoInvoice'

    try:
        remote_invoice = json.loads(response.text)['paymentRequest']
        print('Remote invoice is: ' + str(remote_invoice))
    except:
        print(response.text)
        print("No payment request received. Sleeping 20 seconds")
        time.sleep(20)
        remote_invoice = 'NoInvoice'

    return remote_invoice


#Pay remote invoice

def deposit(invoice):
    '''
    Pays a lightning invoice, works only for LND. 
    Edit the command as needed if C-lightning or other
    '''

    command = ['echo yes | lncli payinvoice '+ invoice]
    with Popen(command, stdout=PIPE, stderr=None, shell=True) as process:
        output = process.communicate()[0].decode("utf-8")
        print(output)
        if 'SUCCEEDED' in str(output):
            return True
        else:
            return False

#Generate local invoice
def gen_local_invoice():
    '''
    Generates a lightning invoice, works only for LND. 
    Edit the command as needed if C-lightning or other
    '''

    out = subprocess.run(["lncli", "addinvoice","--amt", str(int(amount_sats))], capture_output = True)
    local_invoice = json.loads(out.stdout)["payment_request"]
    print("Local Invoice is: " + str(local_invoice))

    return local_invoice

#Withdraw to local invoice
def withdraw(invoice):
    url = "https://api.lnmarkets.com/v1/user/withdraw"
    payload = {
        "amount": amount_sats,
        "unit": "sat",
        "invoice": invoice}
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": "Bearer " + LNMToken
    }

    if use_tor:
        response = session.request("POST", url, json=payload, headers=headers)
    else:
        response = requests.request("POST", url, json=payload, headers=headers)

    print(response.text)
    return is_error(response.text)

def is_error(api_return):

    if 'HttpError' in str(api_return):
        print('Error found! Sleeping 60 seconds')
        print(str(api_return))
        time.sleep(60)
        return True

    return False

##################
#   Main loop!   #
##################
start0 = time.time()
start = time.time()

epsilon=0.00000001 # a tiny number

for i in range(iterations):

    end = time.time()
    print("Elapsed time cycle "+str(i)+": "+ str(end - start) + " avg is "+ str((end - start0)/(i+epsilon)) )
    start = time.time()

    #Try an Except the whole thing just in case
    try:
        print("################## DEPOSITING ##############")
        deposit_success = deposit(gen_remote_invoice())

        if deposit_success:
            print("################## WITHDRAWING ##############")
            failed_withdrawal = withdraw(gen_local_invoice())
            while failed_withdrawal:
                failed_withdrawal = withdraw(gen_local_invoice())

            if i%5==0:
                #If something goes wrong you will like to know when is a good moment to kill the process. Now it is.
                print("##################################################################################################################################################")
                print("IT IS SAFE TO EXIT (Ctrl+C) FOR 5 SECS")
                print("##################################################################################################################################################")
                time.sleep(5)
        else:
            print("Depositing FAILED. Sleeping 2 minutes.")
            time.sleep(120)
    except:
        print("##############################")
        print("#    There was a WOPSIE :)   #")
        print("##############################")