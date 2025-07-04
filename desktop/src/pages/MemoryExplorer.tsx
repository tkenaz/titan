import React, { useState } from 'react'
import { Trash2, Search, Tag, Brain, X } from 'lucide-react'
import { SearchBar } from '../components/common/SearchBar'
import { DataTable } from '../components/common/DataTable'
import { 
  useSearchMemoriesQuery, 
  useDeleteMemoryMutation,
  Memory 
} from '../api/memoryApi'
import { format } from 'date-fns'

interface MemoryDrawerProps {
  memory: Memory & { score?: number }
  onClose: () => void
  onDelete: () => void
}

const MemoryDrawer: React.FC<MemoryDrawerProps> = ({ memory, onClose, onDelete }) => {
  const [deleteMemory, { isLoading }] = useDeleteMemoryMutation()

  const handleDelete = async () => {
    try {
      await deleteMemory(memory.id).unwrap()
      onDelete()
      onClose()
    } catch (error) {
      console.error('Failed to delete memory:', error)
    }
  }

  return (
    <div className="fixed inset-0 z-50 overflow-hidden">
      <div className="absolute inset-0 bg-black bg-opacity-50" onClick={onClose} />
      <div className="absolute right-0 top-0 h-full w-full max-w-md bg-gray-800 shadow-xl">
        <div className="flex h-full flex-col">
          <div className="flex items-center justify-between border-b border-gray-700 px-6 py-4">
            <h2 className="text-lg font-semibold">Memory Details</h2>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-white transition-colors"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          <div className="flex-1 overflow-y-auto p-6">
            <div className="space-y-6">
              {/* Summary */}
              <div>
                <h3 className="text-sm font-medium text-gray-400 mb-2">Summary</h3>
                <p className="text-white">{memory.summary}</p>
              </div>

              {/* Content */}
              <div>
                <h3 className="text-sm font-medium text-gray-400 mb-2">Full Content</h3>
                <p className="text-gray-300 whitespace-pre-wrap">{memory.content}</p>
              </div>

              {/* Metadata */}
              <div>
                <h3 className="text-sm font-medium text-gray-400 mb-2">Metadata</h3>
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span className="text-sm text-gray-400">Priority</span>
                    <span className="text-sm font-medium">{memory.priority}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-gray-400">Created</span>
                    <span className="text-sm">
                      {format(new Date(memory.created_at), 'PPp')}
                    </span>
                  </div>
                  {memory.score !== undefined && (
                    <div className="flex justify-between">
                      <span className="text-sm text-gray-400">Relevance Score</span>
                      <span className="text-sm font-medium">
                        {(memory.score * 100).toFixed(1)}%
                      </span>
                    </div>
                  )}
                </div>
              </div>

              {/* Tags */}
              {memory.metadata?.tags && (
                <div>
                  <h3 className="text-sm font-medium text-gray-400 mb-2">Tags</h3>
                  <div className="flex flex-wrap gap-2">
                    {memory.metadata.tags.map((tag: string, index: number) => (
                      <span
                        key={index}
                        className="inline-flex items-center gap-1 px-2 py-1 text-xs bg-gray-700 text-gray-300 rounded"
                      >
                        <Tag className="h-3 w-3" />
                        {tag}
                      </span>
                    ))}
                  </div>
                </div>
              )}

              {/* Custom Metadata */}
              {Object.keys(memory.metadata || {}).length > 0 && (
                <div>
                  <h3 className="text-sm font-medium text-gray-400 mb-2">Custom Data</h3>
                  <pre className="text-xs bg-gray-900 p-3 rounded overflow-x-auto">
                    {JSON.stringify(memory.metadata, null, 2)}
                  </pre>
                </div>
              )}
            </div>
          </div>

          <div className="border-t border-gray-700 px-6 py-4">
            <button
              onClick={handleDelete}
              disabled={isLoading}
              className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-red-600 hover:bg-red-700 disabled:bg-red-800 text-white rounded-lg transition-colors"
            >
              <Trash2 className="h-4 w-4" />
              {isLoading ? 'Deleting...' : 'Forget Memory'}
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

export const MemoryExplorer: React.FC = () => {
  const [searchQuery, setSearchQuery] = useState('')
  const [selectedMemory, setSelectedMemory] = useState<(Memory & { score?: number }) | null>(null)
  
  const { data: searchResults, isLoading } = useSearchMemoriesQuery(
    { query: searchQuery, limit: 50 },
    { skip: !searchQuery }
  )

  const handleSearch = () => {
    // Search is triggered automatically by the query
  }

  const memories = searchResults?.memories || []

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold">Memory Explorer</h1>
        <p className="text-gray-400 mt-1">Search and manage stored memories</p>
      </div>

      {/* Search Bar */}
      <SearchBar
        value={searchQuery}
        onChange={setSearchQuery}
        onSubmit={handleSearch}
        placeholder="Search memories by content or metadata..."
        showHistory={true}
      />

      {/* Results */}
      {searchQuery && (
        <div>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold">
              {isLoading ? 'Searching...' : `${memories.length} results found`}
            </h2>
          </div>

          <DataTable
            data={memories}
            loading={isLoading}
            emptyMessage="No memories found matching your search"
            onRowClick={setSelectedMemory}
            columns={[
              {
                key: 'summary',
                label: 'Summary',
                render: (memory) => (
                  <div className="max-w-md">
                    <p className="text-white font-medium truncate">{memory.summary}</p>
                    <p className="text-xs text-gray-400 truncate mt-1">{memory.content}</p>
                  </div>
                )
              },
              {
                key: 'score',
                label: 'Relevance',
                render: (memory) => (
                  <div className="flex items-center gap-2">
                    <div className="w-16 h-2 bg-gray-700 rounded-full overflow-hidden">
                      <div 
                        className="h-full bg-blue-500"
                        style={{ width: `${(memory.score || 0) * 100}%` }}
                      />
                    </div>
                    <span className="text-xs text-gray-400">
                      {((memory.score || 0) * 100).toFixed(0)}%
                    </span>
                  </div>
                )
              },
              {
                key: 'priority',
                label: 'Priority',
                render: (memory) => (
                  <span className={`
                    px-2 py-1 text-xs rounded
                    ${memory.priority >= 8 ? 'bg-red-900 text-red-300' :
                      memory.priority >= 5 ? 'bg-yellow-900 text-yellow-300' :
                      'bg-gray-700 text-gray-300'}
                  `}>
                    {memory.priority}
                  </span>
                )
              },
              {
                key: 'metadata',
                label: 'Tags',
                render: (memory) => (
                  <div className="flex gap-1">
                    {(memory.metadata?.tags || []).slice(0, 3).map((tag: string, i: number) => (
                      <span key={i} className="text-xs bg-gray-700 px-2 py-1 rounded">
                        {tag}
                      </span>
                    ))}
                    {(memory.metadata?.tags?.length || 0) > 3 && (
                      <span className="text-xs text-gray-500">
                        +{memory.metadata.tags.length - 3}
                      </span>
                    )}
                  </div>
                )
              },
              {
                key: 'created_at',
                label: 'Created',
                render: (memory) => (
                  <span className="text-sm text-gray-400">
                    {format(new Date(memory.created_at), 'MMM d, yyyy')}
                  </span>
                )
              }
            ]}
          />
        </div>
      )}

      {/* Empty State */}
      {!searchQuery && (
        <div className="bg-gray-800 rounded-lg border border-gray-700 p-12">
          <div className="text-center">
            <Brain className="h-12 w-12 text-gray-600 mx-auto mb-4" />
            <h3 className="text-lg font-medium text-gray-300 mb-2">
              Search Your Memory
            </h3>
            <p className="text-gray-500 max-w-md mx-auto">
              Enter a search query above to find relevant memories. You can search by content,
              tags, or any metadata stored with the memories.
            </p>
          </div>
        </div>
      )}

      {/* Memory Detail Drawer */}
      {selectedMemory && (
        <MemoryDrawer
          memory={selectedMemory}
          onClose={() => setSelectedMemory(null)}
          onDelete={() => {
            // Refetch will happen automatically due to tag invalidation
          }}
        />
      )}
    </div>
  )
}
