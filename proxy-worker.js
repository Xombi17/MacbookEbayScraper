export default {
  async fetch(request) {
    const url = new URL(request.url);
    const targetUrl = url.searchParams.get("url");
    
    if (!targetUrl) {
      return new Response("MacBook Deal Proxy Active. Send ?url=EBAY_URL", { status: 200 });
    }

    const response = await fetch(targetUrl, {
      headers: {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/rss+xml, application/xml"
      }
    });

    return new Response(response.body, {
      headers: { 
        "Content-Type": "application/rss+xml",
        "Access-Control-Allow-Origin": "*" 
      }
    });
  }
};
