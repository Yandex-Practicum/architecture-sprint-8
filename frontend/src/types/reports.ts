export interface Report {
  id: string;
  name: string;
  createdAt: string;
  status: 'pending' | 'ready' | 'failed';
  fileUrl?: string;
}

export interface GenerateReportRequest {
  type: 'sales' | 'users' | 'revenue';
  dateFrom: string;
  dateTo: string;
  format: 'pdf' | 'excel';
}