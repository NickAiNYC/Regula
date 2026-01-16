/**
 * Regula Health - Type Definitions
 * TypeScript interfaces for the application
 */

export interface User {
  id: string;
  email: string;
  full_name: string | null;
  role: string;
  is_active: boolean;
  organization_id: string;
  created_at: string;
}

export interface Organization {
  id: string;
  name: string;
  ein: string | null;
  is_active: boolean;
  subscription_tier: string | null;
  created_at: string;
}

export interface Claim {
  id: string;
  provider_id: string;
  claim_id: string;
  payer: string;
  payer_id: string | null;
  dos: string; // Date
  cpt_code: string;
  units: number;
  billed_amount: number | null;
  mandate_rate: number;
  paid_amount: number;
  delta: number;
  is_violation: boolean;
  geo_adjustment_factor: number | null;
  processing_date: string | null;
  created_at: string;
}

export interface ClaimFilter {
  payer?: string;
  cpt_code?: string;
  dos_start?: string;
  dos_end?: string;
  is_violation?: boolean;
  page?: number;
  per_page?: number;
}

export interface ClaimListResponse {
  claims: Claim[];
  total: number;
  page: number;
  per_page: number;
  has_next: boolean;
}

export interface DashboardMetrics {
  total_claims: number;
  violations: number;
  violation_rate: number;
  total_recoverable: number;
  avg_underpayment: number;
  top_violators: Array<{
    payer: string;
    violation_count: number;
    total_amount: number;
  }>;
  recent_claims: Claim[];
}

export interface PayerStats {
  payer: string;
  total_claims: number;
  violations: number;
  violation_rate: number;
  total_recoverable: number;
}

export interface LoginRequest {
  email: string;
  password: string;
  mfa_code?: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  full_name: string;
  organization_name: string;
  ein?: string;
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
}

export interface EDIUploadResponse {
  message: string;
  file_name: string;
  claims_processed: number;
  violations_found: number;
  processing_time_seconds: number;
}
