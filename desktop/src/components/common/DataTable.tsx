import React from 'react'
import { ChevronLeft, ChevronRight } from 'lucide-react'

interface Column<T> {
  key: keyof T | string
  label: string
  render?: (item: T) => React.ReactNode
  className?: string
}

interface DataTableProps<T> {
  data: T[]
  columns: Column<T>[]
  onRowClick?: (item: T) => void
  pagination?: {
    currentPage: number
    totalPages: number
    onPageChange: (page: number) => void
  }
  loading?: boolean
  emptyMessage?: string
}

export function DataTable<T extends Record<string, any>>({
  data,
  columns,
  onRowClick,
  pagination,
  loading,
  emptyMessage = 'No data available'
}: DataTableProps<T>) {
  if (loading) {
    return (
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-8">
        <div className="flex justify-center items-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-white"></div>
        </div>
      </div>
    )
  }

  if (data.length === 0) {
    return (
      <div className="bg-gray-800 rounded-lg border border-gray-700 p-8">
        <p className="text-center text-gray-400">{emptyMessage}</p>
      </div>
    )
  }

  return (
    <div className="bg-gray-800 rounded-lg border border-gray-700 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-gray-700">
          <thead className="bg-gray-900">
            <tr>
              {columns.map((column) => (
                <th
                  key={column.key}
                  className={`px-6 py-3 text-left text-xs font-medium text-gray-400 uppercase tracking-wider ${
                    column.className || ''
                  }`}
                >
                  {column.label}
                </th>
              ))}
            </tr>
          </thead>
          <tbody className="divide-y divide-gray-700">
            {data.map((item, index) => (
              <tr
                key={index}
                onClick={() => onRowClick?.(item)}
                className={`${
                  onRowClick ? 'cursor-pointer hover:bg-gray-700' : ''
                } transition-colors`}
              >
                {columns.map((column) => (
                  <td
                    key={column.key}
                    className={`px-6 py-4 whitespace-nowrap text-sm text-gray-300 ${
                      column.className || ''
                    }`}
                  >
                    {column.render
                      ? column.render(item)
                      : item[column.key as keyof T]}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {pagination && (
        <div className="bg-gray-900 px-4 py-3 flex items-center justify-between border-t border-gray-700">
          <div className="flex items-center gap-2">
            <button
              onClick={() => pagination.onPageChange(pagination.currentPage - 1)}
              disabled={pagination.currentPage === 1}
              className="p-2 text-gray-400 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronLeft className="w-5 h-5" />
            </button>
            <span className="text-sm text-gray-400">
              Page {pagination.currentPage} of {pagination.totalPages}
            </span>
            <button
              onClick={() => pagination.onPageChange(pagination.currentPage + 1)}
              disabled={pagination.currentPage === pagination.totalPages}
              className="p-2 text-gray-400 hover:text-white disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
            >
              <ChevronRight className="w-5 h-5" />
            </button>
          </div>
        </div>
      )}
    </div>
  )
}
