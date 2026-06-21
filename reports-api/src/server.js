import http from 'node:http';
import crypto from 'node:crypto';

const config = {
  port: Number(process.env.PORT || 8001),
  frontendUrl: process.env.FRONTEND_URL || 'http://localhost:3000',
  authUrl: process.env.AUTH_URL || 'http://bionicpro-auth:8000',
  internalAuthSecret: process.env.INTERNAL_AUTH_SECRET || 'local-internal-secret',
  clickhouseUrl: process.env.CLICKHOUSE_URL || 'http://clickhouse:8123',
  clickhouseDatabase: process.env.CLICKHOUSE_DATABASE || 'bionicpro',
  reportsTable: process.env.REPORTS_TABLE || 'report_mart_cdc',
  cookieSecure: process.env.AUTH_COOKIE_SECURE !== 'false',
  s3Endpoint: process.env.S3_ENDPOINT || 'http://minio:9000',
  s3AccessKey: process.env.S3_ACCESS_KEY || 'minioadmin',
  s3SecretKey: process.env.S3_SECRET_KEY || 'minioadmin',
  s3Bucket: process.env.S3_BUCKET || 'bionicpro-reports',
  s3Region: process.env.S3_REGION || 'us-east-1',
  cdnBaseUrl: process.env.CDN_BASE_URL || 'http://localhost:8082/reports'
};

const SESSION_COOKIE = 'bp_session';
let bucketReady = false;

function parseCookies(req) {
  const raw = req.headers.cookie || '';
  return Object.fromEntries(
    raw
      .split(';')
      .map((part) => part.trim())
      .filter(Boolean)
      .map((part) => {
        const index = part.indexOf('=');
        return [part.slice(0, index), decodeURIComponent(part.slice(index + 1))];
      })
  );
}

function sendJson(res, status, payload, extraHeaders = {}) {
  res.writeHead(status, {
    'Content-Type': 'application/json',
    'Access-Control-Allow-Origin': config.frontendUrl,
    'Access-Control-Allow-Credentials': 'true',
    ...extraHeaders
  });
  res.end(JSON.stringify(payload));
}

function cookie(name, value, options = {}) {
  const attrs = [
    `${name}=${encodeURIComponent(value)}`,
    'Path=/',
    'HttpOnly',
    `SameSite=${options.sameSite || 'Lax'}`
  ];

  if (config.cookieSecure) {
    attrs.push('Secure');
  }

  if (options.maxAge !== undefined) {
    attrs.push(`Max-Age=${options.maxAge}`);
  }

  return attrs.join('; ');
}

function handleOptions(_req, res) {
  res.writeHead(204, {
    'Access-Control-Allow-Origin': config.frontendUrl,
    'Access-Control-Allow-Credentials': 'true',
    'Access-Control-Allow-Methods': 'GET,OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type'
  });
  res.end();
}

function escapeSql(value) {
  return String(value).replaceAll('\\', '\\\\').replaceAll("'", "\\'");
}

function sha256Hex(value) {
  return crypto.createHash('sha256').update(value).digest('hex');
}

function hmac(key, value, encoding) {
  return crypto.createHmac('sha256', key).update(value).digest(encoding);
}

function awsDate(date = new Date()) {
  const iso = date.toISOString().replace(/[:-]|\.\d{3}/g, '');
  return {
    amzDate: iso,
    dateStamp: iso.slice(0, 8)
  };
}

function encodePath(pathname) {
  return pathname
    .split('/')
    .map((part) => encodeURIComponent(part))
    .join('/');
}

function signS3Request(method, pathname, body = '', canonicalQuery = '') {
  const url = new URL(config.s3Endpoint);
  const { amzDate, dateStamp } = awsDate();
  const payloadHash = sha256Hex(body);
  const canonicalUri = encodePath(pathname);
  const canonicalHeaders = [
    `host:${url.host}`,
    `x-amz-content-sha256:${payloadHash}`,
    `x-amz-date:${amzDate}`
  ].join('\n') + '\n';
  const signedHeaders = 'host;x-amz-content-sha256;x-amz-date';
  const canonicalRequest = [
    method,
    canonicalUri,
    canonicalQuery,
    canonicalHeaders,
    signedHeaders,
    payloadHash
  ].join('\n');
  const credentialScope = `${dateStamp}/${config.s3Region}/s3/aws4_request`;
  const stringToSign = [
    'AWS4-HMAC-SHA256',
    amzDate,
    credentialScope,
    sha256Hex(canonicalRequest)
  ].join('\n');
  const dateKey = hmac(`AWS4${config.s3SecretKey}`, dateStamp);
  const regionKey = hmac(dateKey, config.s3Region);
  const serviceKey = hmac(regionKey, 's3');
  const signingKey = hmac(serviceKey, 'aws4_request');
  const signature = hmac(signingKey, stringToSign, 'hex');

  return {
    Authorization: `AWS4-HMAC-SHA256 Credential=${config.s3AccessKey}/${credentialScope}, SignedHeaders=${signedHeaders}, Signature=${signature}`,
    'x-amz-content-sha256': payloadHash,
    'x-amz-date': amzDate
  };
}

async function s3Request(method, key = '', body = '', headers = {}) {
  const pathname = key ? `/${config.s3Bucket}/${key}` : `/${config.s3Bucket}`;
  const requestHeaders = {
    ...signS3Request(method, pathname, body),
    ...headers
  };

  const response = await fetch(`${config.s3Endpoint}${pathname}`, {
    method,
    headers: requestHeaders,
    body: method === 'GET' || method === 'HEAD' ? undefined : body
  });

  return response;
}

async function ensureBucket() {
  if (bucketReady) {
    return;
  }

  const head = await s3Request('HEAD');
  if (head.ok) {
    await ensureBucketPolicy();
    bucketReady = true;
    return;
  }

  if (head.status !== 404) {
    const details = await head.text();
    throw new Error(`S3 bucket check failed: ${head.status} ${details}`);
  }

  const create = await s3Request('PUT');
  if (!create.ok) {
    const details = await create.text();
    throw new Error(`S3 bucket create failed: ${create.status} ${details}`);
  }

  await ensureBucketPolicy();
  bucketReady = true;
}

async function ensureBucketPolicy() {
  const policy = JSON.stringify({
    Version: '2012-10-17',
    Statement: [
      {
        Effect: 'Allow',
        Principal: { AWS: ['*'] },
        Action: ['s3:GetObject'],
        Resource: [`arn:aws:s3:::${config.s3Bucket}/*`]
      }
    ]
  });
  const pathname = `/${config.s3Bucket}`;
  const url = `${config.s3Endpoint}${pathname}?policy=`;
  const requestHeaders = {
    ...signS3Request('PUT', pathname, policy, 'policy='),
    'Content-Type': 'application/json'
  };
  const response = await fetch(url, {
    method: 'PUT',
    headers: requestHeaders,
    body: policy
  });

  if (!response.ok) {
    const details = await response.text();
    throw new Error(`S3 bucket policy update failed: ${response.status} ${details}`);
  }
}

function reportObjectKey(report) {
  const period = `${report.periodStart}_${report.periodEnd}`
    .replaceAll(' ', 'T')
    .replaceAll(':', '-');
  return `${report.userId}/${report.prosthesisId}/${period}.json`;
}

function cdnUrl(key) {
  return `${config.cdnBaseUrl}/${key}`;
}

async function reportExists(key) {
  const response = await s3Request('HEAD', key);
  if (response.ok) {
    return true;
  }

  if (response.status === 404) {
    return false;
  }

  const details = await response.text();
  throw new Error(`S3 report check failed: ${response.status} ${details}`);
}

async function saveReport(key, report) {
  const body = JSON.stringify({
    report,
    generatedAt: new Date().toISOString()
  }, null, 2);
  const response = await s3Request('PUT', key, body, {
    'Content-Type': 'application/json',
    'Cache-Control': 'public, max-age=3600'
  });

  if (!response.ok) {
    const details = await response.text();
    throw new Error(`S3 report upload failed: ${response.status} ${details}`);
  }
}

async function validateSession(req) {
  const sessionId = parseCookies(req)[SESSION_COOKIE];
  if (!sessionId) {
    return null;
  }

  const response = await fetch(`${config.authUrl}/internal/session/validate`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Internal-Auth-Secret': config.internalAuthSecret
    },
    body: JSON.stringify({ sessionId })
  });

  if (!response.ok) {
    return null;
  }

  return response.json();
}

async function queryClickHouse(sql) {
  const url = new URL('/', config.clickhouseUrl);
  url.searchParams.set('database', config.clickhouseDatabase);
  url.searchParams.set('query', sql);

  const response = await fetch(url, {
    method: 'POST'
  });

  if (!response.ok) {
    const details = await response.text();
    throw new Error(`ClickHouse query failed: ${response.status} ${details}`);
  }

  return response.text();
}

function mapReportRow(row) {
  const [
    userId,
    userName,
    prosthesisId,
    periodStart,
    periodEnd,
    eventsCount,
    avgReactionMs,
    minBatteryLevel,
    lastPreparedAt
  ] = row.split('\t');

  return {
    userId,
    userName,
    prosthesisId,
    periodStart,
    periodEnd,
    eventsCount: Number(eventsCount),
    avgReactionMs: Number(avgReactionMs),
    minBatteryLevel: Number(minBatteryLevel),
    lastPreparedAt
  };
}

async function getOwnReport(user) {
  const username = escapeSql(user.username);
  const sql = `
    SELECT
      user_id,
      user_name,
      prosthesis_id,
      toString(period_start),
      toString(period_end),
      events_count,
      avg_reaction_ms,
      min_battery_level,
      toString(last_prepared_at)
    FROM ${config.reportsTable} FINAL
    WHERE user_id = '${username}'
    ORDER BY period_end DESC
    LIMIT 1
    FORMAT TabSeparated
  `;
  const raw = (await queryClickHouse(sql)).trim();
  return raw ? mapReportRow(raw) : null;
}

async function handleReports(req, res) {
  const session = await validateSession(req);
  if (!session?.user) {
    sendJson(res, 401, { error: 'not_authenticated' });
    return;
  }

  const headers = session.sessionId
    ? {
        'Set-Cookie': cookie(SESSION_COOKIE, session.sessionId, {
          maxAge: session.sessionMaxAge || 1800
        })
      }
    : {};

  const report = await getOwnReport(session.user);
  if (!report) {
    sendJson(res, 404, {
      error: 'report_not_ready',
      message: 'Report is not available yet. Wait until the Airflow DAG prepares the OLAP mart.'
    }, headers);
    return;
  }

  await ensureBucket();
  const key = reportObjectKey(report);
  let cacheStatus = 'hit';

  if (!(await reportExists(key))) {
    await saveReport(key, report);
    cacheStatus = 'miss';
  }

  sendJson(res, 200, {
    report,
    url: cdnUrl(key),
    storageKey: key,
    source: cacheStatus === 'hit' ? 's3' : 'clickhouse',
    cacheStatus,
    generatedAt: new Date().toISOString()
  }, headers);
}

async function router(req, res) {
  try {
    const url = new URL(req.url, `http://${req.headers.host}`);

    if (req.method === 'OPTIONS') {
      handleOptions(req, res);
      return;
    }

    if (req.method === 'GET' && url.pathname === '/health') {
      sendJson(res, 200, { ok: true });
      return;
    }

    if (req.method === 'GET' && url.pathname === '/reports') {
      await handleReports(req, res);
      return;
    }

    sendJson(res, 404, { error: 'not_found' });
  } catch (error) {
    console.error(error);
    sendJson(res, 500, { error: 'server_error', message: error.message });
  }
}

http.createServer(router).listen(config.port, () => {
  console.log(`reports-api listening on ${config.port}`);
});
