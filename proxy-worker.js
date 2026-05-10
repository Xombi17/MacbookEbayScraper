export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const targetUrl = url.searchParams.get("url");
    
    if (!targetUrl) {
      return new Response("MacBook Deal Proxy Active. Send ?url=EBAY_URL", { status: 200 });
    }

    if (!env.FIRECRAWL_API_KEY) {
      return new Response("Missing FIRECRAWL_API_KEY environment variable", { status: 500 });
    }

    try {
      const firecrawlResponse = await fetch("https://api.firecrawl.dev/v1/scrape", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "Authorization": `Bearer ${env.FIRECRAWL_API_KEY}`
        },
        body: JSON.stringify({
          url: targetUrl,
          formats: ["rawHtml"]
        })
      });

      if (!firecrawlResponse.ok) {
        return new Response(`Firecrawl API error: ${firecrawlResponse.statusText}`, { status: 502 });
      }

      const data = await firecrawlResponse.json();
      
      // Firecrawl returns the raw page source in data.rawHtml if 'rawHtml' format is requested
      const rawContent = data?.data?.rawHtml || data?.data?.html || "";

      return new Response(rawContent, {
        headers: { 
          "Content-Type": "application/rss+xml",
          "Access-Control-Allow-Origin": "*" 
        }
      });
    } catch (error) {
      return new Response(`Proxy Error: ${error.message}`, { status: 500 });
    }
  }
};
