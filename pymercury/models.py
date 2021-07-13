import json
import requests
from uuid import uuid4
from datetime import datetime, timedelta
import pytz

utc = pytz.UTC
from dateparser import parse
import pandas as pd

from .GLOBALS import (MEMORY_PATH)
from .helpers import (get_key, save_mem, get_recipient_data, handle_date_string, proc_dates)


class Client:
    def __init__(self, key_path: str, api_version: int = 1):
        with open(MEMORY_PATH, 'r') as f:
            self.memory = json.loads(f.read())
        self.api_version = api_version
        self.base_url = f'https://backend.mercury.com/api/v{api_version}/'
        self.key = get_key(key_path)

        self.update_frequency = timedelta(seconds=5)
        self.last_updated = datetime.now()

        self.recipients = self.get_recipients
        self._recipients = self.get_recipients(as_init=True)

        self.accounts = self.get_accounts
        self._accounts = self.get_accounts(as_init=True)  # Storage of account data.

    def get_accounts(self, as_init=False):
        if datetime.now() - self.last_updated > self.update_frequency or as_init:
            print('Updating account data from remote.')
            self._accounts = self._get_accounts()
        return self._accounts

    def _get_accounts(self):
        print('Getting accounts...')
        url = self.base_url + 'accounts'
        response = requests.get(url, auth=(self.key, '')).json()
        if response.get('errors'):
            print(response['errors']['message'])
            return None

        response['auth_key'] = self.key
        response['client'] = self

        result = parse_accounts_response(response)

        self.last_updated = datetime.now()

        return result

    def get_account(self, id):
        response = requests.get(self.base_url + f'account/{id}', auth=(self.key, '')).json()

        response['auth_key'] = self.key
        response['client'] = self

        return parse_single_account_response(response)

    def get_recipients(self, as_init=False):
        if datetime.now() - self.last_updated > self.update_frequency or as_init:
            print('Updating account data from remote.')
            self._recipients = self._get_recipients()
        return self._recipients

    def _get_recipients(self):
        print('Getting recipients...')
        url = self.base_url + 'recipients'
        response = requests.get(url, auth=(self.key, '')).json()
        if response.get('errors'):
            print(response['errors']['message'])
            return None

        response['auth_key'] = self.key
        response['client'] = self

        result = parse_recipients_response(response)

        self.last_updated = datetime.now()

        return result

    def get_recipient(self, id):
        url = self.base_url + f'recipient/{id}'
        response = requests.get(url, auth=(self.key, '')).json()

        response['auth_key'] = self.key
        response['client'] = self

        return parse_single_recipient_response(response)

    def add_recipient(self, payload=None):
        url = self.base_url + 'recipients'

        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        if not payload:
            # Don't know why this works... but it does. I think?
            rec = Recipient(**dict({'auth_key': self.key, 'client': self}, **json.loads(get_recipient_data())))
            pl = rec.__dict__.copy()
            pl.pop('auth_key')
            pl.pop('client')
            payload = pl

        response = requests.post(url, json=payload, headers=headers, auth=(self.key, ''))

        return response.json()


class Recipient:
    def __init__(self, **kwargs):
        self.client = kwargs['client']
        self.auth_key = kwargs['auth_key']

        # Required attributes:
        self.id = kwargs['id']
        self.name = kwargs['name']
        self.status = kwargs['status']
        self.dateLastPaid = kwargs.get('dateLastPaid', "N/A")
        self.defaultPaymentMethod = kwargs['defaultPaymentMethod']
        self.emails = kwargs['emails']

        # Optional? Attributes:
        try:
            self.electronicRoutingInfo = kwargs['electronicRoutingInfo']
            if self.electronicRoutingInfo != None:
                self.accountNumber = kwargs['electronicRoutingInfo']['accountNumber']
                self.routingNumber = kwargs['electronicRoutingInfo']['routingNumber']
        except:
            pass

    def __repr__(self):
        return f'{self.name} (Last Paid: {self.dateLastPaid})'


def parse_recipients_response(res):
    recipients = {d['name']: Recipient(**dict({'auth_key': res['auth_key'], 'client': res['client']}, **d)) for d in
                  res['recipients']}
    return recipients


def parse_single_recipient_response(res):
    return Recipient(**res)


class Account:
    def __init__(self,
                 **kwargs
                 ):
        self.client = kwargs['client']
        self.auth_key = kwargs['auth_key']
        self.id = kwargs['id']
        self.accountNumber = kwargs['accountNumber']
        self.routingNumber = kwargs['routingNumber']
        self.name = kwargs['name']
        self.status = kwargs['status']
        self.type = kwargs['type']
        self.createdAt = kwargs['createdAt']
        self.availableBalance = kwargs['availableBalance']
        self.currentBalance = kwargs['currentBalance']
        self.kind = kwargs['kind']
        self.canReceiveTransactions = kwargs['canReceiveTransactions']
        self.nickname = kwargs.get('nickname', self.name)

        self.as_recipient = self._get_self_as_recipient()

    def __repr__(self):
        return f'{self.nickname} ({self.name} #{self.accountNumber})'

    def _get_self_as_recipient(self):

        for k, v in self.client.recipients().items():
            v_acct_num = getattr(v, 'accountNumber', None)
            if v_acct_num == self.accountNumber:
                return v

        print(f'No recipient found for {self} - add one with client.add_recipient()!')

        return None

    def send(self, amount: float, to, method='ach'):
        '''
        Send an amount to a recipient.
        :param amount: Amount in USD (float)
        :param to: Where to send (Recipient)
        :return: Transaction confirmation
        '''

        url = f"https://backend.mercury.com/api/v1/account/{self.id}/transactions"

        payload = {
            "recipientId": f"{to.id}",
            "amount": amount,
            "paymentMethod": method,
            "idempotencyKey": str(uuid4())
        }
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

        print(f'Sending ${amount} to {to.name}!')

        response = requests.request("POST", url, json=payload, headers=headers, auth=(self.auth_key, ''))

        return response.json()

    def transactions(self, limit: int = None, offset: int = 0, status: str = None, start: str = None, end: str = None,
                     search: str = None, as_df=False):
        url = f'{self.client.base_url}account/{self.id}/transactions'

        params = {
            'offset': offset,
        }
        if limit:
            params['limit'] = limit
        if status:
            assert status in ["pending", "sent", "cancelled",
                              "failed"], 'Status must be "pending" | "sent" | "cancelled" | "failed"'
            params['status'] = status

        if search:
            params['search'] = search

        resp = requests.get(url, json=params, auth=(self.auth_key, '')).json()
        if as_df:
            if start:
                start = utc.localize(parse(start))
            else:
                start = utc.localize(parse('Jan 1 1800'))
            if end:
                end = utc.localize(parse(end))
            else:
                end = utc.localize(datetime.now())
            resp = pd.read_json(json.dumps(resp['transactions']))
            resp[['createdAt', 'postedAt', 'estimatedDeliveryDate']] = resp[
                ['createdAt', 'postedAt', 'estimatedDeliveryDate']].applymap(proc_dates)
            return resp[resp.createdAt.between(start, end)]

        return resp

    def refresh(self):
        pass


def parse_single_account_response(res):
    return Account(**res)


def parse_accounts_response(res):
    accounts = {d['nickname']: Account(**dict({'auth_key': res['auth_key'], 'client': res['client']}, **d)) for d in
                res['accounts']}
    return accounts
