const express = require('express')
const Keycloak = require('keycloak-connect');
const cors = require('cors')
const Jwt = require("jsonwebtoken");

const keycloakConfig = {
  clientId: process.env.CLIENT_ID,
  bearerOnly: true,
  serverUrl: process.env.KEYCLOAK_SERVER_URL,
  realm: process.env.REALM,
  credentials: {
    secret: process.env.CLIENT_SECRET,
  },
};

const keycloak = new Keycloak({}, keycloakConfig);

const app = express()
const port = 8000

app.use(cors())

app.get('/', (req, res) => {
  res.send('Hello World!')
})

//route protected with Keycloak
app.get(
  '/reports',
  async function(req, res) {
    const token = req.headers?.authorization?.split(" ")[1];
    const check = await keycloak.grantManager
      .validateAccessToken(token);

    if (!check) {
      return res.status(401).send();
    }

    await keycloak.grantManager
      .validateAccessToken(token)

    const decoded = Jwt.decode(token);

    if (!decoded.realm_access.roles.includes('prothetic_user')) {
      return res.status(401).send();
    }

    res.json({
      data: {
        reports: [
          {
            id: 1,
            reportData: {
              name: 'TestReport'
            }
          },
          {
            id: 2,
            reportData: {
              name: 'TestReport'
            }
          }
        ]
      }
    });
  }
);

app.listen(port, () => {
  console.log(`Example app listening on port ${port}`)
})
