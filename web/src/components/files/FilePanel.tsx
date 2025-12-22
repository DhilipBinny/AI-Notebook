'use client'

import { useState, useCallback, useRef, useEffect } from 'react'
import { files as filesApi } from '@/lib/api'
import {
  FolderOpen,
  File,
  Upload,
  Download,
  Trash2,
  Save,
  RefreshCw,
  ChevronRight,
  ChevronDown,
  X,
  FileText,
  FileCode,
  FileJson,
  FileImage,
  FileArchive,
  Table,
  MoreVertical,
} from 'lucide-react'

interface FileInfo {
  name: string
  path: string
  size: number
  is_directory: boolean
  modified_at: string | null
}

interface FilePanelProps {
  projectId: string
  isPlaygroundRunning: boolean
  onClose?: () => void
}

// Format file size for display
function formatFileSize(bytes: number): string {
  if (bytes === 0) return '0 B'
  const k = 1024
  const sizes = ['B', 'KB', 'MB', 'GB']
  const i = Math.floor(Math.log(bytes) / Math.log(k))
  return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i]
}

// Get file icon based on extension
function getFileIcon(filename: string) {
  const ext = filename.split('.').pop()?.toLowerCase() || ''

  switch (ext) {
    case 'py':
    case 'js':
    case 'ts':
    case 'jsx':
    case 'tsx':
    case 'r':
    case 'sql':
      return <FileCode className="w-4 h-4 text-blue-400" />
    case 'json':
    case 'yaml':
    case 'yml':
    case 'toml':
      return <FileJson className="w-4 h-4 text-yellow-400" />
    case 'csv':
    case 'xlsx':
    case 'xls':
    case 'parquet':
      return <Table className="w-4 h-4 text-green-400" />
    case 'png':
    case 'jpg':
    case 'jpeg':
    case 'gif':
    case 'svg':
    case 'webp':
      return <FileImage className="w-4 h-4 text-purple-400" />
    case 'zip':
    case 'tar':
    case 'gz':
    case '7z':
      return <FileArchive className="w-4 h-4 text-orange-400" />
    case 'md':
    case 'txt':
    case 'pdf':
      return <FileText className="w-4 h-4 text-gray-400" />
    default:
      return <File className="w-4 h-4 text-gray-400" />
  }
}

export default function FilePanel({ projectId, isPlaygroundRunning, onClose }: FilePanelProps) {
  const [fileList, setFileList] = useState<FileInfo[]>([])
  const [totalSize, setTotalSize] = useState(0)
  const [isLoading, setIsLoading] = useState(false)
  const [isUploading, setIsUploading] = useState(false)
  const [isSaving, setIsSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)
  const [expandedDirs, setExpandedDirs] = useState<Set<string>>(new Set(['.']))
  const [selectedFile, setSelectedFile] = useState<string | null>(null)
  const [contextMenu, setContextMenu] = useState<{ x: number; y: number; file: FileInfo } | null>(null)
  const [isDragging, setIsDragging] = useState(false)

  const fileInputRef = useRef<HTMLInputElement>(null)
  const dropZoneRef = useRef<HTMLDivElement>(null)

  // Refresh file list
  const refreshFiles = useCallback(async () => {
    if (!isPlaygroundRunning) {
      setFileList([])
      setTotalSize(0)
      return
    }

    setIsLoading(true)
    setError(null)
    try {
      const result = await filesApi.list(projectId)
      setFileList(result.files)
      setTotalSize(result.total_size)
    } catch (err) {
      console.error('Failed to list files:', err)
      setError('Failed to load files')
    } finally {
      setIsLoading(false)
    }
  }, [projectId, isPlaygroundRunning])

  // Initial load
  useEffect(() => {
    refreshFiles()
  }, [refreshFiles])

  // Clear success message after 3 seconds
  useEffect(() => {
    if (successMessage) {
      const timer = setTimeout(() => setSuccessMessage(null), 3000)
      return () => clearTimeout(timer)
    }
  }, [successMessage])

  // Handle file upload
  const handleUpload = useCallback(async (files: FileList | File[]) => {
    if (!isPlaygroundRunning) {
      setError('Playground must be running to upload files')
      return
    }

    const fileArray = Array.from(files)
    if (fileArray.length === 0) return

    setIsUploading(true)
    setError(null)
    try {
      if (fileArray.length === 1) {
        await filesApi.upload(projectId, fileArray[0])
      } else {
        await filesApi.uploadMultiple(projectId, fileArray)
      }
      setSuccessMessage(`Uploaded ${fileArray.length} file(s)`)
      await refreshFiles()
    } catch (err: unknown) {
      console.error('Upload failed:', err)
      const message = err instanceof Error ? err.message : 'Upload failed'
      setError(message)
    } finally {
      setIsUploading(false)
    }
  }, [projectId, isPlaygroundRunning, refreshFiles])

  // Handle file download
  const handleDownload = useCallback(async (file: FileInfo) => {
    try {
      const blobUrl = await filesApi.download(projectId, file.path)
      const a = document.createElement('a')
      a.href = blobUrl
      a.download = file.name
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(blobUrl)
    } catch (err) {
      console.error('Download failed:', err)
      setError('Failed to download file')
    }
  }, [projectId])

  // Handle file delete
  const handleDelete = useCallback(async (file: FileInfo) => {
    if (!confirm(`Delete "${file.name}"?`)) return

    try {
      await filesApi.delete(projectId, [file.path])
      setSuccessMessage(`Deleted ${file.name}`)
      await refreshFiles()
      setSelectedFile(null)
    } catch (err) {
      console.error('Delete failed:', err)
      setError('Failed to delete file')
    }
  }, [projectId, refreshFiles])

  // Save workspace to S3
  const handleSaveToS3 = useCallback(async () => {
    setIsSaving(true)
    setError(null)
    try {
      const result = await filesApi.saveToS3(projectId)
      setSuccessMessage(`Saved ${result.files_saved} files to cloud`)
    } catch (err) {
      console.error('Save failed:', err)
      setError('Failed to save files')
    } finally {
      setIsSaving(false)
    }
  }, [projectId])

  // Drag and drop handlers
  const handleDragEnter = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(true)
  }, [])

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    // Only set dragging to false if leaving the drop zone entirely
    if (dropZoneRef.current && !dropZoneRef.current.contains(e.relatedTarget as Node)) {
      setIsDragging(false)
    }
  }, [])

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
  }, [])

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault()
    e.stopPropagation()
    setIsDragging(false)

    const files = e.dataTransfer.files
    if (files.length > 0) {
      handleUpload(files)
    }
  }, [handleUpload])

  // Context menu handlers
  const handleContextMenu = useCallback((e: React.MouseEvent, file: FileInfo) => {
    e.preventDefault()
    setContextMenu({ x: e.clientX, y: e.clientY, file })
  }, [])

  // Close context menu on click elsewhere
  useEffect(() => {
    const handleClick = () => setContextMenu(null)
    document.addEventListener('click', handleClick)
    return () => document.removeEventListener('click', handleClick)
  }, [])

  // Toggle directory expansion
  const toggleDir = useCallback((path: string) => {
    setExpandedDirs(prev => {
      const next = new Set(prev)
      if (next.has(path)) {
        next.delete(path)
      } else {
        next.add(path)
      }
      return next
    })
  }, [])

  // Build tree structure from flat file list
  const buildTree = useCallback((files: FileInfo[]) => {
    // Group files by parent directory
    const rootFiles: FileInfo[] = []
    const dirContents: Record<string, FileInfo[]> = {}

    files.forEach(file => {
      const parts = file.path.split('/')
      if (parts.length === 1) {
        rootFiles.push(file)
      } else {
        const parent = parts.slice(0, -1).join('/')
        if (!dirContents[parent]) {
          dirContents[parent] = []
        }
        dirContents[parent].push(file)
      }
    })

    return { rootFiles, dirContents }
  }, [])

  // Render file tree item
  const renderFileItem = (file: FileInfo, depth: number = 0) => {
    const isSelected = selectedFile === file.path
    const isExpanded = expandedDirs.has(file.path)

    return (
      <div key={file.path}>
        <div
          className={`flex items-center gap-2 px-2 py-1.5 cursor-pointer rounded text-sm transition-colors ${
            isSelected
              ? 'bg-blue-500/20 text-blue-300'
              : 'hover:bg-white/5 text-gray-300'
          }`}
          style={{ paddingLeft: `${8 + depth * 16}px` }}
          onClick={() => {
            setSelectedFile(file.path)
            if (file.is_directory) {
              toggleDir(file.path)
            }
          }}
          onContextMenu={(e) => handleContextMenu(e, file)}
        >
          {file.is_directory ? (
            <>
              {isExpanded ? (
                <ChevronDown className="w-3 h-3 text-gray-500" />
              ) : (
                <ChevronRight className="w-3 h-3 text-gray-500" />
              )}
              <FolderOpen className="w-4 h-4 text-yellow-400" />
            </>
          ) : (
            <>
              <span className="w-3" /> {/* Spacer for alignment */}
              {getFileIcon(file.name)}
            </>
          )}
          <span className="flex-1 truncate">{file.name}</span>
          {!file.is_directory && (
            <span className="text-xs text-gray-500">{formatFileSize(file.size)}</span>
          )}
          <button
            onClick={(e) => {
              e.stopPropagation()
              handleContextMenu(e as unknown as React.MouseEvent, file)
            }}
            className="p-1 opacity-0 group-hover:opacity-100 hover:bg-white/10 rounded"
          >
            <MoreVertical className="w-3 h-3" />
          </button>
        </div>
      </div>
    )
  }

  const { rootFiles } = buildTree(fileList)

  return (
    <div className="h-full flex flex-col bg-slate-900/95 border-r border-white/10">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-white/10">
        <div className="flex items-center gap-2">
          <FolderOpen className="w-4 h-4 text-gray-400" />
          <span className="text-sm font-medium text-white">Files</span>
          {fileList.length > 0 && (
            <span className="text-xs text-gray-500">({formatFileSize(totalSize)})</span>
          )}
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={refreshFiles}
            disabled={!isPlaygroundRunning || isLoading}
            className="p-1.5 text-gray-400 hover:text-white hover:bg-white/10 rounded transition-colors disabled:opacity-50"
            title="Refresh"
          >
            <RefreshCw className={`w-4 h-4 ${isLoading ? 'animate-spin' : ''}`} />
          </button>
          {onClose && (
            <button
              onClick={onClose}
              className="p-1.5 text-gray-400 hover:text-white hover:bg-white/10 rounded transition-colors"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>
      </div>

      {/* Toolbar */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-white/10">
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={!isPlaygroundRunning || isUploading}
          className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs bg-blue-600 hover:bg-blue-500 text-white rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
        >
          <Upload className="w-3.5 h-3.5" />
          {isUploading ? 'Uploading...' : 'Upload'}
        </button>
        <button
          onClick={handleSaveToS3}
          disabled={!isPlaygroundRunning || isSaving || fileList.length === 0}
          className="flex items-center gap-1.5 px-2.5 py-1.5 text-xs bg-green-600 hover:bg-green-500 text-white rounded transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          title="Save files to cloud storage"
        >
          <Save className="w-3.5 h-3.5" />
          {isSaving ? 'Saving...' : 'Save'}
        </button>
        <input
          ref={fileInputRef}
          type="file"
          multiple
          className="hidden"
          onChange={(e) => {
            if (e.target.files) {
              handleUpload(e.target.files)
              e.target.value = '' // Reset input
            }
          }}
        />
      </div>

      {/* Status messages */}
      {error && (
        <div className="px-3 py-2 bg-red-500/10 border-b border-red-500/20 text-red-400 text-xs">
          {error}
        </div>
      )}
      {successMessage && (
        <div className="px-3 py-2 bg-green-500/10 border-b border-green-500/20 text-green-400 text-xs">
          {successMessage}
        </div>
      )}

      {/* File list / Drop zone */}
      <div
        ref={dropZoneRef}
        className={`flex-1 overflow-y-auto ${isDragging ? 'bg-blue-500/10' : ''}`}
        onDragEnter={handleDragEnter}
        onDragLeave={handleDragLeave}
        onDragOver={handleDragOver}
        onDrop={handleDrop}
      >
        {!isPlaygroundRunning ? (
          <div className="flex flex-col items-center justify-center h-full text-center p-4">
            <FolderOpen className="w-10 h-10 text-gray-600 mb-3" />
            <p className="text-sm text-gray-500 mb-1">Playground not running</p>
            <p className="text-xs text-gray-600">Start the playground to manage files</p>
          </div>
        ) : isLoading && fileList.length === 0 ? (
          <div className="flex items-center justify-center h-full">
            <RefreshCw className="w-6 h-6 text-gray-500 animate-spin" />
          </div>
        ) : fileList.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center p-4">
            <Upload className="w-10 h-10 text-gray-600 mb-3" />
            <p className="text-sm text-gray-500 mb-1">No files yet</p>
            <p className="text-xs text-gray-600">
              {isDragging ? 'Drop files here' : 'Drag & drop files or click Upload'}
            </p>
          </div>
        ) : (
          <div className="py-1">
            {isDragging && (
              <div className="mx-2 my-1 p-4 border-2 border-dashed border-blue-500 rounded-lg text-center text-blue-400 text-sm">
                Drop files here to upload
              </div>
            )}
            {rootFiles.map(file => renderFileItem(file))}
          </div>
        )}
      </div>

      {/* Context menu */}
      {contextMenu && (
        <div
          className="fixed z-50 bg-slate-800 border border-white/10 rounded-lg shadow-xl py-1 min-w-[140px]"
          style={{ left: contextMenu.x, top: contextMenu.y }}
        >
          {!contextMenu.file.is_directory && (
            <button
              onClick={() => {
                handleDownload(contextMenu.file)
                setContextMenu(null)
              }}
              className="w-full flex items-center gap-2 px-3 py-1.5 text-sm text-gray-300 hover:bg-white/10 transition-colors"
            >
              <Download className="w-4 h-4" />
              Download
            </button>
          )}
          <button
            onClick={() => {
              handleDelete(contextMenu.file)
              setContextMenu(null)
            }}
            className="w-full flex items-center gap-2 px-3 py-1.5 text-sm text-red-400 hover:bg-white/10 transition-colors"
          >
            <Trash2 className="w-4 h-4" />
            Delete
          </button>
        </div>
      )}
    </div>
  )
}
