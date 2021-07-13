import os

import requests
import json
from uuid import uuid4
from dateparser import parse


def get_key(key_path):
    with open(key_path, 'r') as f:
        return f.read()


def save_mem(path, mem):
    with open(path, 'w') as f:
        f.write(json.dumps(mem))


def ask(prompt, field_type=str, default=None):
    response = input(prompt)
    if response:
        return field_type(response)
    else:
        return default


def process_template(template):
    # Template is dict of field : (valueType, default)
    result = dict()

    for field, item in template.items():
        if isinstance(item, tuple) and field != 'emails':
            (field_type, default) = item

            if field_type == dict:
                proceed = (input(f'Step into "{field}"? (y/n): ').upper() == 'Y')
                if proceed:
                    # Recurse into sub-dict.
                    result[field] = process_template(default)
                else:
                    result[field] = None
            else:
                result[field] = ask(field, field_type=field_type, default=default)
        else:
            result[field] = item

    return result


def get_recipient_data():
    template = {
        "name": (str, None),
        "address": (dict, {
            "address1": (str, None),
            "address2": (str, None),
            "city": (str, None),
            "region": (str, None),
            "postalCode": (str, None),
            "country": (str, None),
        }),  # Template is dict of key : (valueType, default)
        "dateLastPaid": None,
        "paymentMethod": (str, 'ach'),
        "domesticWireRoutingInfo": (dict, {
            "accountNumber": (str, None),
            "bankName": (str, None),
            "routingNumber": (str, None),
            "electronicAccountType": "businessChecking",
            "address": (dict, {
                "address1": (str, None),
                "address2": (str, None),
                "city": (str, None),
                "region": (str, None),
                "postalCode": (str, None),
                "country": (str, None),
            }),
        }),
        "electronicRoutingInfo": (dict, {
            "accountNumber": (str, None),
            "bankName": (str, None),
            "routingNumber": (str, None),
            "electronicAccountType": "businessChecking",
            "address": (dict, {
                "address1": (str, None),
                "address2": (str, None),
                "city": (str, None),
                "region": (str, None),
                "postalCode": (str, None),
                "country": (str, None),

            })
        }),
        "emails": [
            os.environ['MERCURY_EMAIL']
        ],
        "id": str(uuid4()),
        "internationalWireRoutingInfo": None,
        "status": 'active'  # (str, None)
    }

    result = process_template(template)
    with open('last_recipient.json', 'w') as f:
        f.write(json.dumps(result))

    return json.dumps(result)


def handle_date_string(date_string):
    dt = parse(date_string)
    # Mercury format: YYYY-MM-DD
    formatted = f'{dt.year}-{str(dt.month).zfill(2)}-{str(dt.day).zfill(2)}'
    return formatted


def proc_dates(s):
    if isinstance(s, str):
        return parse(s)


if __name__ == '__main__':
    print(get_recipient_data())
