import { NextResponse } from "next/server";
import OpenAI from "openai";

export const runtime = "nodejs";

const VALID_ACCELERATORS = ["yc", "ef", "spc", "a16z_speedrun"];
const VALID_STATUSES = ["Active", "Acquired", "Public", "Dead", "Unknown"];

export async function POST(req: Request) {
  const apiKey = process.env.XAI_API_KEY;
  if (!apiKey) {
    return NextResponse.json(
      { error: "XAI_API_KEY not configured on server" },
      { status: 500 }
    );
  }
  const { query, industries } = (await req.json()) as {
    query: string;
    industries: string[];
  };
  if (!query?.trim()) {
    return NextResponse.json({ error: "empty query" }, { status: 400 });
  }

  const client = new OpenAI({
    apiKey,
    baseURL: "https://api.x.ai/v1",
  });

  const system = `You translate English queries into a STRICT JSON filter object for a startup directory.

Valid accelerator slugs (enum): ${VALID_ACCELERATORS.join(", ")}
Valid statuses (enum):           ${VALID_STATUSES.join(", ")}
Valid industry labels (enum):    ${industries.join(", ")}

Shape of output (omit keys that aren't implied by the query):
{
  "search":        string (free text to match in name/description),
  "accelerators":  string[] (subset of accelerator slugs),
  "statuses":      string[] (subset of statuses),
  "industries":    string[] (subset of industry labels; use exact strings above),
  "yearMin":       number (founded year, inclusive),
  "yearMax":       number (founded year, inclusive),
  "topOnly":       boolean (true if user wants only "top companies"),
  "hiringOnly":    boolean,
  "withWebsite":   boolean,
  "withLinkedIn":  boolean,
  "serialOnly":    boolean (true if user asks for repeat/serial founders),
  "rationale":     string (one short sentence describing what you applied)
}

Rules:
- Return ONLY valid JSON. No markdown, no commentary.
- Map shorthand: "ycomb"/"Y Combinator" -> "yc"; "speedrun"/"a16z" -> "a16z_speedrun"; "EF"/"Entrepreneur First" -> "ef"; "SPC" -> "spc".
- Map "AI companies", "LLM startups", etc. to the closest industry label above (e.g. "AI & ML Infrastructure").
- "failed"/"shut down" -> statuses: ["Dead"]. "exits" -> ["Acquired","Public"].
- If the query mentions a cohort year, set both yearMin and yearMax to that year.
- NEVER invent industry labels that aren't in the enum.
- If nothing maps, return {"rationale":"could not map"}.`;

  try {
    const res = await client.chat.completions.create({
      model: "grok-4-fast-non-reasoning",
      messages: [
        { role: "system", content: system },
        { role: "user", content: query },
      ],
      response_format: { type: "json_object" },
      temperature: 0,
      max_tokens: 500,
    });
    const text = res.choices[0]?.message?.content ?? "{}";
    const parsed = JSON.parse(text);

    // Sanitize enum fields
    if (Array.isArray(parsed.accelerators)) {
      parsed.accelerators = parsed.accelerators.filter((a: string) =>
        VALID_ACCELERATORS.includes(a)
      );
    }
    if (Array.isArray(parsed.statuses)) {
      parsed.statuses = parsed.statuses.filter((s: string) =>
        VALID_STATUSES.includes(s)
      );
    }
    if (Array.isArray(parsed.industries)) {
      parsed.industries = parsed.industries.filter((i: string) =>
        industries.includes(i)
      );
    }

    return NextResponse.json(parsed);
  } catch (e) {
    const msg = e instanceof Error ? e.message : String(e);
    return NextResponse.json({ error: msg }, { status: 500 });
  }
}
