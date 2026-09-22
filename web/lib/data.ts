import "server-only";

import { promises as fs } from "fs";
import path from "path";

import type {
  Batch,
  Budget,
  Company,
  CoverageRow,
  Insight,
  SerialFounder,
  Summary,
} from "./types";

// Public builds read the committed, founder-free sample (`make sample`).
// Set ATLAS_DATA_DIR=data locally to read the full export (`make export`).
const DATA_DIR = path.join(process.cwd(), "public", process.env.ATLAS_DATA_DIR ?? "sample");

async function loadJSON<T>(name: string): Promise<T> {
  const buf = await fs.readFile(path.join(DATA_DIR, name), "utf-8");
  return JSON.parse(buf) as T;
}

export async function getSummary(): Promise<Summary> {
  return loadJSON<Summary>("summary.json");
}

export async function getCompanies(): Promise<Company[]> {
  return loadJSON<Company[]>("companies.json");
}

export async function getBatches(): Promise<Batch[]> {
  return loadJSON<Batch[]>("batches.json");
}

export async function getInsights(): Promise<{ insights: Insight[]; budget: Budget }> {
  return loadJSON<{ insights: Insight[]; budget: Budget }>("insights.json");
}

export async function getCoverage(): Promise<CoverageRow[]> {
  return loadJSON<CoverageRow[]>("coverage.json");
}

export async function getSerialFounders(): Promise<SerialFounder[]> {
  return loadJSON<SerialFounder[]>("founders.json");
}
