/**
 * Regula Health - Dashboard Page
 * Real-time analytics and metrics display
 */

import { useQuery } from '@tanstack/react-query';
import { apiClient } from '@/services/api';
import { DashboardMetrics } from '@/types';
import { DollarSign, AlertTriangle, TrendingUp, FileText } from 'lucide-react';
import { formatCurrency, formatPercent } from '@/utils/format';

export function Dashboard() {
  const { data: metrics, isLoading, error, refetch } = useQuery<DashboardMetrics>({
    queryKey: ['dashboard-metrics'],
    queryFn: async () => {
      const response = await apiClient.getDashboardMetrics(30);
      return response.data;
    },
    refetchInterval: 5000, // Refresh every 5 seconds
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-xl">Loading dashboard...</div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-xl text-red-500">Error loading dashboard</div>
      </div>
    );
  }

  return (
    <div className="p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold text-white">Dashboard</h1>
        <button
          onClick={() => refetch()}
          className="px-4 py-2 bg-primary-600 text-white rounded-lg hover:bg-primary-700 transition"
        >
          Refresh
        </button>
      </div>

      {/* Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <MetricCard
          title="Total Claims"
          value={metrics?.total_claims || 0}
          icon={<FileText className="w-6 h-6" />}
          color="blue"
        />
        <MetricCard
          title="Violations Found"
          value={metrics?.violations || 0}
          icon={<AlertTriangle className="w-6 h-6" />}
          color="red"
        />
        <MetricCard
          title="Violation Rate"
          value={formatPercent(metrics?.violation_rate || 0)}
          icon={<TrendingUp className="w-6 h-6" />}
          color="yellow"
        />
        <MetricCard
          title="Recoverable Amount"
          value={formatCurrency(metrics?.total_recoverable || 0)}
          icon={<DollarSign className="w-6 h-6" />}
          color="green"
        />
      </div>

      {/* Top Violators */}
      <div className="bg-slate-800 rounded-lg p-6">
        <h2 className="text-xl font-semibold text-white mb-4">Top Violators</h2>
        <div className="space-y-3">
          {metrics?.top_violators.map((violator, index) => (
            <div
              key={index}
              className="flex items-center justify-between p-4 bg-slate-700 rounded-lg"
            >
              <div>
                <div className="font-medium text-white">{violator.payer}</div>
                <div className="text-sm text-gray-400">
                  {violator.violation_count} violations
                </div>
              </div>
              <div className="text-right">
                <div className="font-semibold text-red-400">
                  {formatCurrency(violator.total_amount)}
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Recent Claims */}
      <div className="bg-slate-800 rounded-lg p-6">
        <h2 className="text-xl font-semibold text-white mb-4">Recent Claims</h2>
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="text-left text-gray-400 border-b border-slate-700">
                <th className="pb-3">Claim ID</th>
                <th className="pb-3">Payer</th>
                <th className="pb-3">CPT Code</th>
                <th className="pb-3">DOS</th>
                <th className="pb-3">Paid</th>
                <th className="pb-3">Mandate</th>
                <th className="pb-3">Delta</th>
                <th className="pb-3">Status</th>
              </tr>
            </thead>
            <tbody>
              {metrics?.recent_claims.map((claim) => (
                <tr
                  key={claim.id}
                  className="border-b border-slate-700 hover:bg-slate-700 transition"
                >
                  <td className="py-3 text-white">{claim.claim_id}</td>
                  <td className="py-3 text-white">{claim.payer}</td>
                  <td className="py-3 text-white">{claim.cpt_code}</td>
                  <td className="py-3 text-white">
                    {new Date(claim.dos).toLocaleDateString()}
                  </td>
                  <td className="py-3 text-white">
                    {formatCurrency(claim.paid_amount)}
                  </td>
                  <td className="py-3 text-white">
                    {formatCurrency(claim.mandate_rate)}
                  </td>
                  <td className="py-3 text-white">
                    {formatCurrency(claim.delta)}
                  </td>
                  <td className="py-3">
                    {claim.is_violation ? (
                      <span className="px-2 py-1 bg-red-500/20 text-red-400 rounded text-sm">
                        Violation
                      </span>
                    ) : (
                      <span className="px-2 py-1 bg-green-500/20 text-green-400 rounded text-sm">
                        Compliant
                      </span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}

interface MetricCardProps {
  title: string;
  value: number | string;
  icon: React.ReactNode;
  color: 'blue' | 'red' | 'yellow' | 'green';
}

function MetricCard({ title, value, icon, color }: MetricCardProps) {
  const colors = {
    blue: 'bg-blue-500/20 text-blue-400',
    red: 'bg-red-500/20 text-red-400',
    yellow: 'bg-yellow-500/20 text-yellow-400',
    green: 'bg-green-500/20 text-green-400',
  };

  return (
    <div className="bg-slate-800 rounded-lg p-6 border border-slate-700">
      <div className="flex items-center justify-between mb-4">
        <div className={`p-3 rounded-lg ${colors[color]}`}>{icon}</div>
      </div>
      <div className="text-3xl font-bold text-white mb-1">{value}</div>
      <div className="text-sm text-gray-400">{title}</div>
    </div>
  );
}
