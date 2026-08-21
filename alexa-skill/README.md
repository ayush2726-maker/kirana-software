# Kirana Software Alexa Skill

This folder contains an AWS Lambda based Alexa Custom Skill that connects to the existing Kirana Software FastAPI backend. Billing is still created through `/api/sales`, so existing stock, ledger and invoice rules remain in one place.

## Included voice actions

- Select customer
- Add an item to the current bill
- Remove the last item
- Complete and save the bill
- Check an item rate
- Check a customer balance
- Read today's sales
- Cancel the current bill

Example flow:

- "Alexa, open Kirana Software"
- "Customer Rajesh"
- "Kabuli 1 kg add karo"
- "Sugar 2 kg add karo"
- "Bill bana do"

## 1. Create the Alexa skill

In the Alexa Developer Console create a **Custom** skill named `Kirana Software` for the locale you want to use. Open **Build > Interaction Model > JSON Editor** and paste the contents of `interaction-model.json`, then save and build the model.

## 2. Create the Lambda function

Create an AWS Lambda function using a currently supported Python runtime in the same Alexa-supported AWS region used by your skill.

Build a deployment package locally:

```bash
mkdir package
pip install -r requirements.txt -t package
cp lambda_function.py package/
cd package
zip -r ../kirana-alexa.zip .
```

Upload `kirana-alexa.zip` to the Lambda function and set the handler to:

```text
lambda_function.lambda_handler
```

## 3. Configure Kirana backend access

Set these Lambda environment variables:

```text
KIRANA_API_URL=https://YOUR-KIRANA-RAILWAY-DOMAIN
KIRANA_USERNAME=YOUR_KIRANA_USERNAME
KIRANA_PASSWORD=YOUR_KIRANA_PASSWORD
```

Alternatively, set `KIRANA_TOKEN` instead of username/password. Username/password is preferred for this first version because the backend login token expires and the Lambda code can automatically log in again after a 401 response.

Do not put credentials inside `lambda_function.py` or commit them to GitHub.

## 4. Connect Lambda to Alexa

Copy the Lambda ARN. In the Alexa Developer Console open **Build > Endpoint**, choose **AWS Lambda ARN**, and paste the ARN for the skill locale. Add the Alexa Skills Kit trigger to the Lambda function if the console does not create it automatically.

## 5. Test

Use the Alexa Developer Console **Test** tab first. Test at least these commands:

```text
open kirana software
customer Rajesh
Kabuli 1 kg add karo
bill bana do
Rajesh ka balance batao
Kabuli 1 kg ka rate batao
aaj ki sale batao
```

Only test bill creation with a test customer/item first because `CompleteBillIntent` creates a real sale in the connected Kirana database.

## Security note

The Alexa request terminates at AWS Lambda and the ASK SDK handles the Alexa request envelope there. The Lambda then calls the existing Kirana HTTPS API using normal Kirana authentication. No public unauthenticated billing endpoint is added to the Railway backend.

## Current limitation

This first version keeps the bill cart in the Alexa session. If the Alexa session ends before `bill bana do`, the unsaved cart is lost. A later version can persist drafts server-side and can add account linking for multiple Kirana businesses/users.
