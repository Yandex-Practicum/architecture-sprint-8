const express = require("express");
const cors = require("cors");
const jwt = require("jsonwebtoken");
const axios = require("axios");

const app = express();

const jwksUrl = new URL(
  "http://keycloak:8080/realms/reports-realm/protocol/openid-connect/certs"
);

app.use(
  cors({
    origin: "*",
  })
);
app.use(express.json());

const generateRandomReports = (count = 5) => {
  const reportTypes = ["sales", "inventory", "users", "performance", "errors"];
  const statuses = ["completed", "failed", "pending", "processing"];

  return Array.from({ length: count }, (_, i) => ({
    id: `report-${Date.now()}-${i}`,
    type: reportTypes[Math.floor(Math.random() * reportTypes.length)],
    status: statuses[Math.floor(Math.random() * statuses.length)],
    createdAt: new Date(
      Date.now() - Math.random() * 7 * 24 * 60 * 60 * 1000
    ).toISOString(),
    metrics: {
      processedItems: Math.floor(Math.random() * 1000),
      successRate: Math.random().toFixed(2),
      executionTime: (Math.random() * 10).toFixed(2) + "s",
    },
  }));
};

const getKey = async (header) => {
  const jwks = (await axios.get(jwksUrl))?.data;

  const signingKey = jwks.keys.find((key) => key.kid === header.kid);
  if (!signingKey) {
    throw new Error("Соответствующий ключ не найден");
  }

  const cert = `-----BEGIN CERTIFICATE-----\n${signingKey.x5c[0]}\n-----END CERTIFICATE-----`;
  return cert;
};

// Функция для проверки токена и роли
async function verifyTokenAndRole(token, requiredRole) {
  const decodedToken = jwt.decode(token, { complete: true });

  console.log("ecodedToken: ", decodedToken);

  if (!decodedToken) {
    throw new Error("Неверный токен");
  }

  const key = await getKey(decodedToken.header);

  return new Promise((resolve, reject) => {
    jwt.verify(token, key, (err, decoded) => {
      if (err) {
        return reject(err);
      }

      const roles = decoded?.realm_access?.roles || [];
      if (roles.includes(requiredRole)) {
        resolve(true);
      } else {
        resolve(false);
      }
    });
  });
}

app.get("/reports", async (req, res) => {
  const token = req.headers["authorization"].replace("Bearer ", "");

  verifyTokenAndRole(token, "prothetic_user")
    .then((hasRole) => {
      if (hasRole) {
        const reports = generateRandomReports();

        return res.status(200).json({
          success: true,
          data: reports,
          meta: {
            generatedAt: new Date().toISOString(),
            count: reports.length,
          },
        });
      } else {
        return res.status(403).send("Доступ запрещен");
      }
    })
    .catch((error) => {
      return res.status(401).send("Неверный токен");
    });
});

app.listen(8000, () => {
  console.log(`API eeeee server running on port 8000`);
});
