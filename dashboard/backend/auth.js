import crypto from 'node:crypto';

if (!process.env.DASHBOARD_PASSWORD) {
  console.error('FATAL: DASHBOARD_PASSWORD environment variable is required');
  process.exit(1);
}

const SECRET = crypto.randomBytes(32).toString('hex');

export function generateToken(password) {
  return crypto.createHmac('sha256', SECRET).update(password).digest('hex');
}

export function verifyToken(token) {
  if (!/^[0-9a-f]{64}$/i.test(token)) return false;
  const expected = generateToken(process.env.DASHBOARD_PASSWORD);
  return crypto.timingSafeEqual(
    Buffer.from(token, 'hex'),
    Buffer.from(expected, 'hex')
  );
}

export function requireAuth(req, res, next) {
  const token = req.cookies?.dashboard_auth;
  if (!token) return res.status(401).json({ error: 'Not authenticated' });

  try {
    if (!verifyToken(token)) {
      return res.status(401).json({ error: 'Invalid token' });
    }
  } catch {
    return res.status(401).json({ error: 'Invalid token' });
  }

  next();
}
