/**
 * @file councilApi.ts
 * @description API client utilities for the LangGraph Council Orchestrator.
 */

import { CouncilRosterResponse, CouncilDeliberationState } from '../types';

export async function fetchCouncilRoster(): Promise<CouncilRosterResponse> {
  const response = await fetch('/api/council/roster');
  if (!response.ok) {
    throw new Error(`Failed to fetch Council roster: ${response.statusText}`);
  }
  return response.json();
}

export async function deliberateProposal(
  rawPrompt: string,
  targetAsset: string = 'BTC',
  maxRounds: number = 2
): Promise<CouncilDeliberationState> {
  const response = await fetch('/api/council/deliberate', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      raw_prompt: rawPrompt,
      target_asset: targetAsset,
      max_rounds: maxRounds,
    }),
  });

  if (!response.ok) {
    const errData = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(errData.detail || 'Council deliberation failed');
  }

  const result = await response.json();
  return result.state;
}
