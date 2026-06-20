export async function POST(request) {
  try {
    const authHeader = request.headers.get("authorization");
    const body = await request.json();

    const response = await fetch("http://127.0.0.1:8000/api/auto_post/generate-content", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(authHeader ? { Authorization: authHeader } : {})
      },
      body: JSON.stringify(body)
    });

    const dataText = await response.text();
    return new Response(dataText, {
      status: response.status,
      headers: { "Content-Type": "application/json" }
    });
  } catch (error) {
    return new Response(
      JSON.stringify({ success: false, detail: "Next.js Custom Proxy Error: " + error.message }),
      { status: 500, headers: { "Content-Type": "application/json" } }
    );
  }
}
