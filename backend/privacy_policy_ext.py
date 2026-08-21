from fastapi.responses import HTMLResponse

from backend.app import app


PRIVACY_POLICY_HTML = """<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Kirana Software Privacy Policy</title>
  <style>
    body{font-family:Arial,sans-serif;max-width:860px;margin:40px auto;padding:0 20px;line-height:1.6;color:#172033}
    h1,h2{color:#0b2b55} .muted{color:#667085} a{color:#0b67c2}
  </style>
</head>
<body>
  <h1>Kirana Software Privacy Policy</h1>
  <p class=\"muted\">Last updated: 21 August 2026</p>
  <p>Kirana Software provides billing and shop-management features, including an Alexa voice interface for authorized shop users.</p>

  <h2>Information we process</h2>
  <p>When the Alexa skill is used, Kirana Software may process customer names, item names, quantities, prices, customer balances, sales totals, and other billing information already stored in the authorized Kirana Software account. Alexa request metadata may also be processed as needed to provide the requested voice action.</p>

  <h2>How information is used</h2>
  <p>Information is used only to provide requested functions such as selecting a customer, adding items to a bill, checking rates or balances, viewing sales totals, and creating a sales bill.</p>

  <h2>Data sharing</h2>
  <p>Kirana Software does not sell personal information. Information is shared only with service providers necessary to operate the application and voice integration, such as hosting infrastructure and Amazon Alexa, subject to their applicable terms and privacy practices.</p>

  <h2>Data retention and security</h2>
  <p>Business and billing records are retained according to the shop's operational needs and applicable requirements. Reasonable technical safeguards are used to protect stored information and restrict access to authorized users.</p>

  <h2>Children</h2>
  <p>Kirana Software and its Alexa skill are intended for business/shop use and are not directed to children under 13.</p>

  <h2>Your choices</h2>
  <p>Authorized users can stop using the Alexa skill at any time. Business data can be managed through the Kirana Software application, subject to applicable record-retention requirements.</p>

  <h2>Changes to this policy</h2>
  <p>This policy may be updated when features, legal requirements, or data practices change. The current version will remain available at this URL.</p>

  <h2>Contact</h2>
  <p>For privacy questions, contact the Kirana Software administrator through the support/contact details provided in the Kirana Software application.</p>
</body>
</html>"""


@app.get("/privacy-policy", response_class=HTMLResponse, include_in_schema=False)
def privacy_policy_page():
    return HTMLResponse(PRIVACY_POLICY_HTML)
