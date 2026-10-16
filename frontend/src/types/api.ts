export interface HealthStatus {
  status: string;
  database: string;
  storage?: string;
}

export interface ApiError {
  detail?: string;
  message?: string;
  status?: number;
}
