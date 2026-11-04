/**
 * Cloudflare Pages Function
 * Route: /api/profile?username=...
 * Enforces strict Domain-Level & Same-Origin security.
 * External websites, bots, and third-party servers receive 401 Unauthorized.
 */

function isAuthorizedOrigin(request) {
  const url = new URL(request.url);
  const currentHost = request.headers.get('host') || url.host;
  const origin = request.headers.get('origin');
  const referer = request.headers.get('referer');
  const secFetchSite = request.headers.get('sec-fetch-site');
  const clientSignature = request.headers.get('x-requested-with');

  // 1. Block any cross-site browser fetches
  if (secFetchSite && secFetchSite === 'cross-site') {
    return { authorized: false, reason: 'Cross-site request blocked' };
  }

  // 2. Validate internal client signature
  if (clientSignature !== 'InstaGrowthApp') {
    return { authorized: false, reason: 'Missing authorized client signature' };
  }

  // Helper to test if a hostname matches our authorized site
  const matchesOurDomain = (hostname) => {
    if (!hostname) return false;
    const cleanHost = currentHost.split(':')[0].toLowerCase();
    const h = hostname.toLowerCase();
    return (
      h === cleanHost ||
      h === 'localhost' ||
      h === '127.0.0.1' ||
      h.endsWith('.pages.dev')
    );
  };

  // 3. Validate Origin header if present
  if (origin) {
    try {
      const originHost = new URL(origin).hostname;
      if (!matchesOurDomain(originHost)) {
        return { authorized: false, reason: `Origin ${originHost} not permitted` };
      }
    } catch (e) {
      return { authorized: false, reason: 'Malformed Origin' };
    }
  }

  // 4. Validate Referer header if present
  if (referer) {
    try {
      const refererHost = new URL(referer).hostname;
      if (!matchesOurDomain(refererHost)) {
        return { authorized: false, reason: `Referer ${refererHost} not permitted` };
      }
    } catch (e) {
      return { authorized: false, reason: 'Malformed Referer' };
    }
  }

  // 5. Direct requests without Origin or Referer (curl / external server scraper)
  if (!origin && !referer) {
    return { authorized: false, reason: 'Direct external API access prohibited' };
  }

  return { authorized: true };
}

function extractInstagramUsername(input) {
  if (!input) return '';
  let str = input.trim();

  if (str.includes('instagram.com') || str.includes('instagr.am') || str.startsWith('http://') || str.startsWith('https://')) {
    try {
      let urlStr = str;
      if (!urlStr.startsWith('http://') && !urlStr.startsWith('https://')) {
        urlStr = 'https://' + urlStr;
      }
      const parsed = new URL(urlStr);
      const segments = parsed.pathname.split('/').filter(s => Boolean(s.trim()));
      if (segments.length > 0) {
        let seg = segments[0];
        if ((seg === '_u' || seg === 'profile') && segments[1]) {
          seg = segments[1];
        }
        return seg.replace(/^@/, '').trim();
      }
    } catch (e) {
      const match = str.match(/(?:instagram\.com|instagr\.am)\/([a-zA-Z0-9._]+)/i);
      if (match && match[1]) {
        return match[1].trim();
      }
    }
  }

  let clean = str.split('?')[0].split('#')[0].replace(/^\/+|\/+$/g, '').replace(/^@/, '').trim();
  return clean;
}

export async function onRequestGet(context) {
  const { request, env } = context;
  const url = new URL(request.url);
  const currentOrigin = request.headers.get('origin') || `${url.protocol}//${url.host}`;

  const securityHeaders = {
    'Access-Control-Allow-Origin': currentOrigin,
    'Access-Control-Allow-Methods': 'GET, OPTIONS',
    'Access-Control-Allow-Headers': 'Content-Type, X-Requested-With',
    'Vary': 'Origin, Referer',
    'Content-Type': 'application/json; charset=utf-8'
  };

  // Enforce Domain-Level Blocking
  const auth = isAuthorizedOrigin(request);
  if (!auth.authorized) {
    return new Response(JSON.stringify({
      status: 'error',
      code: 401,
      message: 'Unauthorized: Access restricted to authorized website origin only',
      detail: auth.reason
    }), {
      status: 401,
      headers: securityHeaders
    });
  }

  const rawInput = url.searchParams.get('username') || '';
  const cleanUser = extractInstagramUsername(rawInput);

  if (!cleanUser) {
    return new Response(JSON.stringify({ status: 'error', message: 'Username is required' }), {
      status: 400,
      headers: securityHeaders
    });
  }

  // Read API Key from Cloudflare Pages Environment Variables
  const apiKey = env.SEARCHAPI_API_KEY;
  if (!apiKey) {
    return new Response(JSON.stringify({ 
      status: 'error', 
      message: 'SEARCHAPI_API_KEY environment variable is not configured in Cloudflare Pages settings' 
    }), {
      status: 500,
      headers: securityHeaders
    });
  }

  try {
    const searchApiUrl = `https://www.searchapi.io/api/v1/search?engine=instagram_profile&username=${encodeURIComponent(cleanUser)}&api_key=${encodeURIComponent(apiKey)}`;
    
    const response = await fetch(searchApiUrl, {
      headers: {
        'User-Agent': 'InstaGrowthPro/1.0'
      }
    });

    if (!response.ok) {
      const errText = await response.text();
      let errMsg = `SearchApi responded with status ${response.status}`;
      try {
        const parsed = JSON.parse(errText);
        if (parsed.error) errMsg = parsed.error;
      } catch (e) {}
      return new Response(JSON.stringify({ status: 'error', message: errMsg }), {
        status: response.status,
        headers: securityHeaders
      });
    }

    const data = await response.json();
    const profile = data.profile;

    if (!profile) {
      return new Response(JSON.stringify({
        status: 'error',
        message: data.error || 'Profile not found or is private'
      }), {
        status: 404,
        headers: securityHeaders
      });
    }

    // Normalized profile schema
    const extracted = {
      username: profile.username || cleanUser,
      name: profile.name || cleanUser,
      bio: profile.bio || '',
      avatar: profile.avatar || '',
      is_verified: Boolean(profile.is_verified),
      posts: Number(profile.posts || 0),
      followers: Number(profile.followers || 0),
      following: Number(profile.following || 0),
      external_link: profile.external_link || ''
    };

    return new Response(JSON.stringify({
      status: 'success',
      web_mode: (env.WEB_MODE || 'PUBLIC').trim(),
      profile: extracted
    }), {
      status: 200,
      headers: {
        ...securityHeaders,
        // Cache at Cloudflare Edge for 10 minutes to save SearchApi credits
        'Cache-Control': 'public, max-age=600, s-maxage=600'
      }
    });
  } catch (error) {
    return new Response(JSON.stringify({
      status: 'error',
      message: error.message || 'Internal server error'
    }), {
      status: 500,
      headers: securityHeaders
    });
  }
}

export async function onRequestOptions(context) {
  const { request } = context;
  const url = new URL(request.url);
  const currentOrigin = request.headers.get('origin') || `${url.protocol}//${url.host}`;

  return new Response(null, {
    status: 204,
    headers: {
      'Access-Control-Allow-Origin': currentOrigin,
      'Access-Control-Allow-Methods': 'GET, OPTIONS',
      'Access-Control-Allow-Headers': 'Content-Type, X-Requested-With',
      'Vary': 'Origin, Referer'
    }
  });
}
