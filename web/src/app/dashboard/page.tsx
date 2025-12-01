'use client'

import { useEffect, useState, useCallback, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { auth, projects, playgrounds, notebooks } from '@/lib/api'
import { useAuthStore, useProjectsStore } from '@/lib/store'
import type { Project } from '@/types'

interface PlaygroundStatus {
  [projectId: string]: {
    status: 'stopped' | 'starting' | 'running' | 'stopping' | 'error'
    loading: boolean
    error?: string
    memory_limit_mb?: number
    cpu_limit?: number
  }
}

export default function DashboardPage() {
  const router = useRouter()
  const { user, isLoading: authLoading, setUser } = useAuthStore()
  const { projects: projectList, setProjects, addProject, removeProject } = useProjectsStore()
  const [isLoading, setIsLoading] = useState(true)
  const [showNewProject, setShowNewProject] = useState(false)
  const [newProjectName, setNewProjectName] = useState('')
  const [newProjectDesc, setNewProjectDesc] = useState('')
  const [creating, setCreating] = useState(false)
  const [playgroundStatuses, setPlaygroundStatuses] = useState<PlaygroundStatus>({})
  const [notificationMessage, setNotificationMessage] = useState<string | null>(null)
  const [showImportModal, setShowImportModal] = useState(false)
  const [importProjectName, setImportProjectName] = useState('')
  const [importFile, setImportFile] = useState<File | null>(null)
  const [importing, setImporting] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [editingProject, setEditingProject] = useState<Project | null>(null)
  const [editName, setEditName] = useState('')
  const [editDesc, setEditDesc] = useState('')
  const [updating, setUpdating] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState<Project | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [downloadingProject, setDownloadingProject] = useState<string | null>(null)
  const [logsProject, setLogsProject] = useState<Project | null>(null)
  const [logs, setLogs] = useState<string[]>([])
  const [logsConnected, setLogsConnected] = useState(false)
  const logsWsRef = useRef<WebSocket | null>(null)

  const fetchPlaygroundStatus = useCallback(async (projectId: string) => {
    try {
      const pg = await playgrounds.get(projectId)
      setPlaygroundStatuses(prev => ({
        ...prev,
        [projectId]: {
          status: pg?.status || 'stopped',
          loading: false,
          memory_limit_mb: pg?.memory_limit_mb,
          cpu_limit: pg?.cpu_limit,
        }
      }))
    } catch {
      setPlaygroundStatuses(prev => ({
        ...prev,
        [projectId]: { status: 'stopped', loading: false }
      }))
    }
  }, [])

  // Check for redirect message from notebook page
  useEffect(() => {
    const message = sessionStorage.getItem('notebook_redirect_message')
    if (message) {
      setNotificationMessage(message)
      sessionStorage.removeItem('notebook_redirect_message')
      // Auto-dismiss after 5 seconds
      setTimeout(() => setNotificationMessage(null), 5000)
    }
  }, [])

  useEffect(() => {
    const init = async () => {
      try {
        const token = localStorage.getItem('access_token')
        if (!token) {
          router.push('/auth/login')
          return
        }
        const userData = await auth.getMe()
        setUser(userData)
        const { projects: projectsData } = await projects.list()
        setProjects(projectsData)
        projectsData.forEach((p: Project) => fetchPlaygroundStatus(p.id))
      } catch {
        router.push('/auth/login')
      } finally {
        setIsLoading(false)
      }
    }
    init()
  }, [router, setUser, setProjects, fetchPlaygroundStatus])

  const handleStartPlayground = async (projectId: string) => {
    setPlaygroundStatuses(prev => ({
      ...prev,
      [projectId]: { status: 'starting', loading: true }
    }))
    try {
      const { playground: pg } = await playgrounds.start(projectId)
      setPlaygroundStatuses(prev => ({
        ...prev,
        [projectId]: {
          status: pg.status,
          loading: false,
          memory_limit_mb: pg.memory_limit_mb,
          cpu_limit: pg.cpu_limit,
        }
      }))
    } catch (err) {
      console.error('Failed to start playground:', err)
      setPlaygroundStatuses(prev => ({
        ...prev,
        [projectId]: { status: 'error', loading: false, error: 'Failed to start' }
      }))
    }
  }

  const handleStopPlayground = async (projectId: string) => {
    setPlaygroundStatuses(prev => ({
      ...prev,
      [projectId]: { status: 'stopping', loading: true }
    }))
    try {
      await playgrounds.stop(projectId)
      setPlaygroundStatuses(prev => ({
        ...prev,
        [projectId]: { status: 'stopped', loading: false }
      }))
    } catch (err) {
      console.error('Failed to stop playground:', err)
      setPlaygroundStatuses(prev => ({
        ...prev,
        [projectId]: { status: 'error', loading: false, error: 'Failed to stop' }
      }))
    }
  }

  const handleRestartPlayground = async (projectId: string) => {
    setPlaygroundStatuses(prev => ({
      ...prev,
      [projectId]: { status: 'starting', loading: true }
    }))
    try {
      await playgrounds.stop(projectId)
      const { playground: pg } = await playgrounds.start(projectId)
      setPlaygroundStatuses(prev => ({
        ...prev,
        [projectId]: {
          status: pg.status,
          loading: false,
          memory_limit_mb: pg.memory_limit_mb,
          cpu_limit: pg.cpu_limit,
        }
      }))
    } catch (err) {
      console.error('Failed to restart playground:', err)
      setPlaygroundStatuses(prev => ({
        ...prev,
        [projectId]: { status: 'error', loading: false, error: 'Failed to restart' }
      }))
    }
  }

  const handleCreateProject = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newProjectName.trim()) return
    setCreating(true)
    try {
      const project = await projects.create({
        name: newProjectName.trim(),
        description: newProjectDesc.trim() || undefined,
      })
      addProject(project)
      setShowNewProject(false)
      setNewProjectName('')
      setNewProjectDesc('')

      setPlaygroundStatuses(prev => ({
        ...prev,
        [project.id]: { status: 'starting', loading: true }
      }))
      try {
        const { playground: pg } = await playgrounds.start(project.id)
        setPlaygroundStatuses(prev => ({
          ...prev,
          [project.id]: {
            status: pg.status,
            loading: false,
            memory_limit_mb: pg.memory_limit_mb,
            cpu_limit: pg.cpu_limit,
          }
        }))
      } catch {
        setPlaygroundStatuses(prev => ({
          ...prev,
          [project.id]: { status: 'stopped', loading: false }
        }))
      }
    } catch (err) {
      console.error('Failed to create project:', err)
    } finally {
      setCreating(false)
    }
  }

  const handleDeleteProject = (project: Project) => {
    setDeleteConfirm(project)
  }

  const confirmDeleteProject = async () => {
    if (!deleteConfirm) return

    setDeleting(true)
    try {
      const status = playgroundStatuses[deleteConfirm.id]
      if (status?.status === 'running') {
        await playgrounds.stop(deleteConfirm.id)
      }
      await projects.delete(deleteConfirm.id)
      removeProject(deleteConfirm.id)
      setPlaygroundStatuses(prev => {
        const newStatuses = { ...prev }
        delete newStatuses[deleteConfirm.id]
        return newStatuses
      })
      setDeleteConfirm(null)
      setNotificationMessage('Notebook deleted successfully')
      setTimeout(() => setNotificationMessage(null), 3000)
    } catch (err) {
      console.error('Failed to delete project:', err)
      setNotificationMessage('Failed to delete notebook')
      setTimeout(() => setNotificationMessage(null), 3000)
    } finally {
      setDeleting(false)
    }
  }

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]
    if (file) {
      setImportFile(file)
      // Auto-fill project name from filename (without extension)
      const name = file.name.replace(/\.ipynb$/i, '')
      setImportProjectName(name)
    }
  }

  const handleImportProject = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!importFile || !importProjectName.trim()) return

    setImporting(true)
    try {
      // Read the file content
      const fileContent = await importFile.text()
      const ipynbData = JSON.parse(fileContent)

      // Create the project first
      const project = await projects.create({
        name: importProjectName.trim(),
        description: `Imported from ${importFile.name}`,
      })
      addProject(project)

      // Import the notebook content
      await notebooks.import(project.id, ipynbData)

      // Reset form and close modal
      setShowImportModal(false)
      setImportFile(null)
      setImportProjectName('')
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }

      // Show success notification
      setNotificationMessage(`Successfully imported "${importFile.name}" with notebook cells`)
      setTimeout(() => setNotificationMessage(null), 5000)

      // Start playground
      setPlaygroundStatuses(prev => ({
        ...prev,
        [project.id]: { status: 'starting', loading: true }
      }))
      try {
        const { playground: pg } = await playgrounds.start(project.id)
        setPlaygroundStatuses(prev => ({
          ...prev,
          [project.id]: {
            status: pg.status,
            loading: false,
            memory_limit_mb: pg.memory_limit_mb,
            cpu_limit: pg.cpu_limit,
          }
        }))
      } catch {
        setPlaygroundStatuses(prev => ({
          ...prev,
          [project.id]: { status: 'stopped', loading: false }
        }))
      }
    } catch (err) {
      console.error('Failed to import notebook:', err)
      setNotificationMessage('Failed to import notebook. Please check the file format.')
      setTimeout(() => setNotificationMessage(null), 5000)
    } finally {
      setImporting(false)
    }
  }

  const handleEditProject = (project: Project) => {
    setEditingProject(project)
    setEditName(project.name)
    setEditDesc(project.description || '')
  }

  const handleUpdateProject = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editingProject || !editName.trim()) return

    setUpdating(true)
    try {
      const updated = await projects.update(editingProject.id, {
        name: editName.trim(),
        description: editDesc.trim() || undefined,
      })
      // Update the project in the store
      setProjects(projectList.map(p => p.id === updated.id ? updated : p))
      setEditingProject(null)
      setNotificationMessage('Notebook updated successfully')
      setTimeout(() => setNotificationMessage(null), 3000)
    } catch (err) {
      console.error('Failed to update project:', err)
      setNotificationMessage('Failed to update notebook')
      setTimeout(() => setNotificationMessage(null), 3000)
    } finally {
      setUpdating(false)
    }
  }

  const handleViewLogs = async (project: Project) => {
    setLogsProject(project)
    setLogs([])
    setLogsConnected(false)

    // First fetch initial logs via HTTP
    try {
      const { logs: initialLogs } = await playgrounds.getLogs(project.id, 100)
      if (initialLogs) {
        setLogs(initialLogs.split('\n'))
      }
    } catch (err) {
      console.error('Failed to fetch initial logs:', err)
    }

    // Connect to WebSocket for real-time logs
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const token = localStorage.getItem('access_token')
    const wsUrl = `${wsProtocol}//${window.location.host}/api/projects/${project.id}/playground/logs/stream?token=${token}`

    const ws = new WebSocket(wsUrl)
    logsWsRef.current = ws

    ws.onopen = () => {
      setLogsConnected(true)
      console.log('Logs WebSocket connected')
    }

    ws.onmessage = (event) => {
      const data = event.data
      if (data) {
        setLogs(prev => [...prev, data].slice(-500)) // Keep last 500 lines
      }
    }

    ws.onerror = (error) => {
      console.error('Logs WebSocket error:', error)
      setLogsConnected(false)
    }

    ws.onclose = () => {
      setLogsConnected(false)
      console.log('Logs WebSocket closed')
    }
  }

  const handleCloseLogs = () => {
    if (logsWsRef.current) {
      logsWsRef.current.close()
      logsWsRef.current = null
    }
    setLogsProject(null)
    setLogs([])
    setLogsConnected(false)
  }

  const handleDownloadProject = async (project: Project) => {
    setDownloadingProject(project.id)
    try {
      const ipynbData = await notebooks.export(project.id)
      const blob = new Blob([JSON.stringify(ipynbData, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `${project.name.replace(/[^a-z0-9]/gi, '_')}.ipynb`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)
      setNotificationMessage(`Downloaded "${project.name}.ipynb"`)
      setTimeout(() => setNotificationMessage(null), 3000)
    } catch (err) {
      console.error('Failed to download notebook:', err)
      setNotificationMessage('Failed to download notebook')
      setTimeout(() => setNotificationMessage(null), 3000)
    } finally {
      setDownloadingProject(null)
    }
  }

  const handleLogout = async () => {
    // Stop all running playgrounds before logout
    for (const project of projectList) {
      const status = playgroundStatuses[project.id]
      if (status?.status === 'running') {
        try {
          await playgrounds.stop(project.id)
        } catch {
          // Ignore errors, just try to stop
        }
      }
    }

    try { await auth.logout() } catch {}
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    setUser(null)
    router.push('/auth/login')
  }

  if (isLoading || authLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="w-12 h-12 border-4 border-blue-500/30 border-t-blue-500 rounded-full animate-spin" />
          <span className="text-blue-300 text-sm">Loading your workspace...</span>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-900 via-purple-900 to-slate-900">
      {/* Notification Banner */}
      {notificationMessage && (
        <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 max-w-lg w-full mx-4 animate-in slide-in-from-top duration-300">
          <div className="bg-amber-500/20 border border-amber-500/50 backdrop-blur-xl rounded-xl p-4 flex items-start gap-3 shadow-lg shadow-amber-500/10">
            <div className="flex-shrink-0 w-8 h-8 rounded-full bg-amber-500/30 flex items-center justify-center">
              <svg className="w-5 h-5 text-amber-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
              </svg>
            </div>
            <div className="flex-1">
              <p className="text-amber-200 text-sm">{notificationMessage}</p>
            </div>
            <button
              onClick={() => setNotificationMessage(null)}
              className="flex-shrink-0 text-amber-400 hover:text-amber-200 transition-colors"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
      )}

      {/* Background elements */}
      <div className="fixed inset-0 overflow-hidden pointer-events-none">
        <div className="absolute -top-40 -right-40 w-80 h-80 bg-purple-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20" />
        <div className="absolute -bottom-40 -left-40 w-80 h-80 bg-cyan-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20" />
      </div>

      {/* Header */}
      <header className="relative z-10 border-b border-white/10 backdrop-blur-xl bg-white/5">
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-teal-500 flex items-center justify-center shadow-lg shadow-blue-500/25">
                <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
              </div>
              <div>
                <h1 className="text-xl font-bold text-white">AI Notebook</h1>
                <p className="text-xs text-purple-300">Intelligent Computing Environment</p>
              </div>
            </div>
            <div className="flex items-center gap-6">
              <div className="flex items-center gap-2 px-4 py-2 rounded-full bg-white/5 border border-white/10">
                <div className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                <span className="text-sm text-gray-300">{user?.email}</span>
              </div>
              <button
                onClick={handleLogout}
                className="px-4 py-2 text-sm text-gray-400 hover:text-white transition-colors"
              >
                Sign Out
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="relative z-10 max-w-7xl mx-auto px-6 py-8">
        {/* Hero Section */}
        <div className="mb-10">
          <div className="flex justify-between items-end">
            <div>
              <h2 className="text-4xl font-bold text-white mb-2">
                Welcome back<span className="text-blue-400">.</span>
              </h2>
              <p className="text-gray-400 text-lg">
                Create, explore, and run AI-powered notebooks
              </p>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={() => setShowImportModal(true)}
                className="group px-5 py-3 bg-white/5 hover:bg-white/10 text-white border border-white/10 hover:border-white/20 rounded-xl font-medium transition-all duration-300 flex items-center gap-2"
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                </svg>
                Import .ipynb
              </button>
              <button
                onClick={() => setShowNewProject(true)}
                className="group px-6 py-3 bg-gradient-to-r from-blue-600 to-teal-600 hover:from-blue-500 hover:to-teal-500 text-white rounded-xl font-medium shadow-lg shadow-blue-500/25 hover:shadow-blue-500/40 transition-all duration-300 flex items-center gap-2"
              >
                <svg className="w-5 h-5 transition-transform group-hover:rotate-90 duration-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                </svg>
                New Notebook
              </button>
            </div>
          </div>
        </div>

        {/* Stats Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-10">
          <div className="p-6 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-sm">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-400 text-sm">Total Notebooks</p>
                <p className="text-3xl font-bold text-white mt-1">{projectList.length}</p>
              </div>
              <div className="w-12 h-12 rounded-xl bg-purple-500/20 flex items-center justify-center">
                <svg className="w-6 h-6 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                </svg>
              </div>
            </div>
          </div>
          <div className="p-6 rounded-2xl bg-white/5 border border-white/10 backdrop-blur-sm">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-gray-400 text-sm">Active Playgrounds</p>
                <p className="text-3xl font-bold text-white mt-1">
                  {Object.values(playgroundStatuses).filter(s => s.status === 'running').length}
                </p>
              </div>
              <div className="w-12 h-12 rounded-xl bg-emerald-500/20 flex items-center justify-center">
                <svg className="w-6 h-6 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
                </svg>
              </div>
            </div>
          </div>
        </div>

        {/* Section Title */}
        <div className="flex items-center gap-3 mb-6">
          <h3 className="text-xl font-semibold text-white">Your Notebooks</h3>
          <div className="flex-1 h-px bg-gradient-to-r from-white/20 to-transparent" />
        </div>

        {/* Projects Grid */}
        {projectList.length === 0 ? (
          <div className="text-center py-20">
            <div className="w-20 h-20 mx-auto mb-6 rounded-2xl bg-white/5 border border-white/10 flex items-center justify-center">
              <svg className="w-10 h-10 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
              </svg>
            </div>
            <h4 className="text-xl font-medium text-white mb-2">No notebooks yet</h4>
            <p className="text-gray-400 mb-6">Create your first AI-powered notebook to get started</p>
            <button
              onClick={() => setShowNewProject(true)}
              className="px-6 py-3 bg-gradient-to-r from-blue-600 to-teal-600 text-white rounded-xl font-medium shadow-lg shadow-blue-500/25 hover:shadow-blue-500/40 transition-all"
            >
              Create Notebook
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {projectList.map((project) => {
              const pgStatus = playgroundStatuses[project.id] || { status: 'stopped', loading: false }
              const isRunning = pgStatus.status === 'running'
              const isLoading = pgStatus.loading

              return (
                <div
                  key={project.id}
                  className="group relative rounded-2xl bg-white/5 border border-white/10 backdrop-blur-sm overflow-hidden hover:bg-white/10 hover:border-white/20 transition-all duration-300"
                >
                  {/* Gradient accent */}
                  <div className="absolute top-0 left-0 right-0 h-1 bg-gradient-to-r from-blue-500 to-teal-500" />

                  <div className="p-6">
                    {/* Header */}
                    <div className="flex items-start justify-between mb-4">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-teal-500 flex items-center justify-center text-white shadow-lg">
                          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                          </svg>
                        </div>
                        <div>
                          <h4 className="font-semibold text-white group-hover:text-blue-300 transition-colors truncate max-w-[180px]">
                            {project.name}
                          </h4>
                        </div>
                      </div>
                      <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-all">
                        <button
                          onClick={() => handleDownloadProject(project)}
                          disabled={downloadingProject === project.id}
                          className="p-2 text-gray-500 hover:text-cyan-400 hover:bg-cyan-500/10 rounded-lg transition-all disabled:opacity-50"
                          title="Download as .ipynb"
                        >
                          {downloadingProject === project.id ? (
                            <div className="w-4 h-4 border-2 border-cyan-400/30 border-t-cyan-400 rounded-full animate-spin" />
                          ) : (
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                            </svg>
                          )}
                        </button>
                        <button
                          onClick={() => handleEditProject(project)}
                          className="p-2 text-gray-500 hover:text-blue-400 hover:bg-blue-500/10 rounded-lg transition-all"
                          title="Edit notebook"
                        >
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                          </svg>
                        </button>
                        <button
                          onClick={() => handleDeleteProject(project)}
                          className="p-2 text-gray-500 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-all"
                          title="Delete notebook"
                        >
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                          </svg>
                        </button>
                      </div>
                    </div>

                    {/* Description */}
                    {project.description && (
                      <p className="text-sm text-gray-400 mb-4 line-clamp-2">
                        {project.description}
                      </p>
                    )}

                    {/* Status */}
                    <div className="flex items-center gap-2 mb-2">
                      <div className={`w-2 h-2 rounded-full ${
                        pgStatus.status === 'running' ? 'bg-emerald-400 shadow-lg shadow-emerald-400/50' :
                        pgStatus.status === 'starting' || pgStatus.status === 'stopping' ? 'bg-amber-400 animate-pulse' :
                        pgStatus.status === 'error' ? 'bg-red-400' : 'bg-gray-500'
                      }`} />
                      <span className="text-xs text-gray-400">
                        {pgStatus.status === 'running' ? 'Environment Ready' :
                         pgStatus.status === 'starting' ? 'Starting...' :
                         pgStatus.status === 'stopping' ? 'Stopping...' :
                         pgStatus.status === 'error' ? 'Error' : 'Offline'}
                      </span>
                    </div>

                    {/* Resource Info - only show when running */}
                    {isRunning && pgStatus.memory_limit_mb && pgStatus.cpu_limit ? (
                      <div className="mb-4 space-y-2">
                        <div className="flex flex-wrap items-center gap-2 px-3 py-2 rounded-lg bg-emerald-500/10 border border-emerald-500/20">
                          <div className="flex items-center gap-1.5">
                            <svg className="w-3.5 h-3.5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 3v2m6-2v2M9 19v2m6-2v2M5 9H3m2 6H3m18-6h-2m2 6h-2M7 19h10a2 2 0 002-2V7a2 2 0 00-2-2H7a2 2 0 00-2 2v10a2 2 0 002 2zM9 9h6v6H9V9z" />
                            </svg>
                            <span className="text-xs text-emerald-300">{pgStatus.cpu_limit} vCPU</span>
                          </div>
                          <div className="w-px h-3 bg-emerald-500/30" />
                          <div className="flex items-center gap-1.5">
                            <svg className="w-3.5 h-3.5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 11H5m14 0a2 2 0 012 2v6a2 2 0 01-2 2H5a2 2 0 01-2-2v-6a2 2 0 012-2m14 0V9a2 2 0 00-2-2M5 11V9a2 2 0 012-2m0 0V5a2 2 0 012-2h6a2 2 0 012 2v2M7 7h10" />
                            </svg>
                            <span className="text-xs text-emerald-300">{(pgStatus.memory_limit_mb / 1024).toFixed(1)} GB RAM</span>
                          </div>
                          <div className="w-px h-3 bg-emerald-500/30" />
                          <div className="flex items-center gap-1.5">
                            <svg className="w-3.5 h-3.5 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 20l4-16m4 4l4 4-4 4M6 16l-4-4 4-4" />
                            </svg>
                            <span className="text-xs text-emerald-300">Python 3.11</span>
                          </div>
                        </div>
                        {/* Logs button */}
                        <button
                          onClick={() => handleViewLogs(project)}
                          className="w-full px-3 py-1.5 text-xs rounded-lg bg-gray-500/20 hover:bg-gray-500/30 text-gray-300 border border-gray-500/30 transition-all flex items-center justify-center gap-1.5"
                        >
                          <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                          </svg>
                          View Logs
                        </button>
                      </div>
                    ) : (
                      <div className="mb-2" />
                    )}

                    {/* Controls */}
                    <div className="flex gap-2 mb-4">
                      {!isRunning ? (
                        <button
                          onClick={() => handleStartPlayground(project.id)}
                          disabled={isLoading}
                          className="flex-1 px-4 py-2 text-sm bg-emerald-500/20 hover:bg-emerald-500/30 text-emerald-400 border border-emerald-500/30 rounded-xl transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                        >
                          {isLoading ? (
                            <>
                              <div className="w-3 h-3 border-2 border-emerald-400/30 border-t-emerald-400 rounded-full animate-spin" />
                              Starting
                            </>
                          ) : (
                            <>
                              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                              </svg>
                              Start
                            </>
                          )}
                        </button>
                      ) : (
                        <>
                          <button
                            onClick={() => handleStopPlayground(project.id)}
                            disabled={isLoading}
                            className="flex-1 px-3 py-2 text-sm bg-red-500/20 hover:bg-red-500/30 text-red-400 border border-red-500/30 rounded-xl transition-all disabled:opacity-50"
                          >
                            Stop
                          </button>
                          <button
                            onClick={() => handleRestartPlayground(project.id)}
                            disabled={isLoading}
                            className="flex-1 px-3 py-2 text-sm bg-amber-500/20 hover:bg-amber-500/30 text-amber-400 border border-amber-500/30 rounded-xl transition-all disabled:opacity-50"
                          >
                            Restart
                          </button>
                        </>
                      )}
                    </div>

                    {/* Meta */}
                    <div className="flex items-center justify-between text-xs text-gray-500 mb-4 pt-4 border-t border-white/5">
                      <span>{new Date(project.updated_at).toLocaleDateString()}</span>
                    </div>

                    {/* Open Button */}
                    <button
                      onClick={() => router.push(`/notebook/${project.id}`)}
                      disabled={!isRunning}
                      className={`w-full py-3 rounded-xl font-medium transition-all flex items-center justify-center gap-2 ${
                        isRunning
                          ? 'bg-gradient-to-r from-blue-600 to-teal-600 hover:from-blue-500 hover:to-teal-500 text-white shadow-lg shadow-blue-500/25 hover:shadow-blue-500/40'
                          : 'bg-white/5 text-gray-500 cursor-not-allowed border border-white/10'
                      }`}
                    >
                      {isRunning ? (
                        <>
                          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                          </svg>
                          Open Notebook
                        </>
                      ) : (
                        <>
                          <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z" />
                          </svg>
                          Start Environment First
                        </>
                      )}
                    </button>
                  </div>
                </div>
              )
            })}
          </div>
        )}
      </main>

      {/* New Project Modal */}
      {showNewProject && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setShowNewProject(false)} />
          <div className="relative w-full max-w-lg rounded-2xl bg-slate-900 border border-white/10 shadow-2xl overflow-hidden">
            {/* Modal header gradient */}
            <div className="absolute top-0 left-0 right-0 h-32 bg-gradient-to-b from-blue-500/20 to-transparent pointer-events-none" />

            <div className="relative p-8">
              <div className="text-center mb-8">
                <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-blue-500 to-teal-500 flex items-center justify-center shadow-lg shadow-blue-500/25">
                  <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                  </svg>
                </div>
                <h3 className="text-2xl font-bold text-white">Create New Notebook</h3>
                <p className="text-gray-400 mt-1">Set up your AI-powered workspace</p>
              </div>

              <form onSubmit={handleCreateProject} className="space-y-6">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Notebook Name
                  </label>
                  <input
                    type="text"
                    value={newProjectName}
                    onChange={(e) => setNewProjectName(e.target.value)}
                    className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-gray-500 focus:outline-none focus:border-purple-500 focus:ring-1 focus:ring-purple-500 transition-all"
                    placeholder="e.g., Data Analysis Project"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Description <span className="text-gray-500">(optional)</span>
                  </label>
                  <textarea
                    value={newProjectDesc}
                    onChange={(e) => setNewProjectDesc(e.target.value)}
                    className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-gray-500 focus:outline-none focus:border-purple-500 focus:ring-1 focus:ring-purple-500 transition-all resize-none"
                    placeholder="What will you explore?"
                    rows={3}
                  />
                </div>

                <div className="flex gap-3 pt-4">
                  <button
                    type="button"
                    onClick={() => setShowNewProject(false)}
                    className="flex-1 px-6 py-3 rounded-xl border border-white/10 text-gray-300 hover:bg-white/5 transition-all"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={creating}
                    className="flex-1 px-6 py-3 rounded-xl bg-gradient-to-r from-blue-600 to-teal-600 hover:from-blue-500 hover:to-teal-500 text-white font-medium shadow-lg shadow-blue-500/25 disabled:opacity-50 transition-all flex items-center justify-center gap-2"
                  >
                    {creating ? (
                      <>
                        <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        Creating...
                      </>
                    ) : (
                      'Create Notebook'
                    )}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* Import Notebook Modal */}
      {showImportModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setShowImportModal(false)} />
          <div className="relative w-full max-w-lg rounded-2xl bg-slate-900 border border-white/10 shadow-2xl overflow-hidden">
            {/* Modal header gradient */}
            <div className="absolute top-0 left-0 right-0 h-32 bg-gradient-to-b from-cyan-500/20 to-transparent pointer-events-none" />

            <div className="relative p-8">
              <div className="text-center mb-8">
                <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-cyan-500 to-blue-500 flex items-center justify-center shadow-lg shadow-cyan-500/25">
                  <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                  </svg>
                </div>
                <h3 className="text-2xl font-bold text-white">Import Notebook</h3>
                <p className="text-gray-400 mt-1">Upload an existing .ipynb file</p>
              </div>

              <form onSubmit={handleImportProject} className="space-y-6">
                {/* File Upload */}
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Select .ipynb File
                  </label>
                  <div
                    onClick={() => fileInputRef.current?.click()}
                    className={`w-full p-6 rounded-xl border-2 border-dashed transition-all cursor-pointer ${
                      importFile
                        ? 'border-cyan-500/50 bg-cyan-500/10'
                        : 'border-white/20 bg-white/5 hover:border-white/40 hover:bg-white/10'
                    }`}
                  >
                    <input
                      ref={fileInputRef}
                      type="file"
                      accept=".ipynb"
                      onChange={handleFileSelect}
                      className="hidden"
                    />
                    <div className="text-center">
                      {importFile ? (
                        <>
                          <svg className="w-10 h-10 mx-auto mb-2 text-cyan-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                          </svg>
                          <p className="text-cyan-400 font-medium">{importFile.name}</p>
                          <p className="text-gray-500 text-sm mt-1">Click to change file</p>
                        </>
                      ) : (
                        <>
                          <svg className="w-10 h-10 mx-auto mb-2 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                          </svg>
                          <p className="text-gray-400">Click to select a file</p>
                          <p className="text-gray-500 text-sm mt-1">or drag and drop</p>
                        </>
                      )}
                    </div>
                  </div>
                </div>

                {/* Project Name */}
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Notebook Name
                  </label>
                  <input
                    type="text"
                    value={importProjectName}
                    onChange={(e) => setImportProjectName(e.target.value)}
                    className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-gray-500 focus:outline-none focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500 transition-all"
                    placeholder="e.g., My Imported Notebook"
                    required
                  />
                </div>

                <div className="flex gap-3 pt-4">
                  <button
                    type="button"
                    onClick={() => {
                      setShowImportModal(false)
                      setImportFile(null)
                      setImportProjectName('')
                      if (fileInputRef.current) {
                        fileInputRef.current.value = ''
                      }
                    }}
                    className="flex-1 px-6 py-3 rounded-xl border border-white/10 text-gray-300 hover:bg-white/5 transition-all"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={importing || !importFile}
                    className="flex-1 px-6 py-3 rounded-xl bg-gradient-to-r from-cyan-600 to-blue-600 hover:from-cyan-500 hover:to-blue-500 text-white font-medium shadow-lg shadow-cyan-500/25 disabled:opacity-50 transition-all flex items-center justify-center gap-2"
                  >
                    {importing ? (
                      <>
                        <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        Importing...
                      </>
                    ) : (
                      'Import Notebook'
                    )}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* Edit Notebook Modal */}
      {editingProject && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setEditingProject(null)} />
          <div className="relative w-full max-w-lg rounded-2xl bg-slate-900 border border-white/10 shadow-2xl overflow-hidden">
            {/* Modal header gradient */}
            <div className="absolute top-0 left-0 right-0 h-32 bg-gradient-to-b from-blue-500/20 to-transparent pointer-events-none" />

            <div className="relative p-8">
              <div className="text-center mb-8">
                <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-blue-500 to-indigo-500 flex items-center justify-center shadow-lg shadow-blue-500/25">
                  <svg className="w-8 h-8 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                  </svg>
                </div>
                <h3 className="text-2xl font-bold text-white">Edit Notebook</h3>
                <p className="text-gray-400 mt-1">Update notebook details</p>
              </div>

              <form onSubmit={handleUpdateProject} className="space-y-6">
                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Notebook Name
                  </label>
                  <input
                    type="text"
                    value={editName}
                    onChange={(e) => setEditName(e.target.value)}
                    className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all"
                    placeholder="e.g., Data Analysis Project"
                    required
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    Description <span className="text-gray-500">(optional)</span>
                  </label>
                  <textarea
                    value={editDesc}
                    onChange={(e) => setEditDesc(e.target.value)}
                    className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-gray-500 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 transition-all resize-none"
                    placeholder="What will you explore?"
                    rows={3}
                  />
                </div>

                <div className="flex gap-3 pt-4">
                  <button
                    type="button"
                    onClick={() => setEditingProject(null)}
                    className="flex-1 px-6 py-3 rounded-xl border border-white/10 text-gray-300 hover:bg-white/5 transition-all"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={updating}
                    className="flex-1 px-6 py-3 rounded-xl bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-500 hover:to-indigo-500 text-white font-medium shadow-lg shadow-blue-500/25 disabled:opacity-50 transition-all flex items-center justify-center gap-2"
                  >
                    {updating ? (
                      <>
                        <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                        Saving...
                      </>
                    ) : (
                      'Save Changes'
                    )}
                  </button>
                </div>
              </form>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => !deleting && setDeleteConfirm(null)} />
          <div className="relative w-full max-w-md rounded-2xl bg-slate-900 border border-red-500/30 shadow-2xl overflow-hidden">
            {/* Modal header gradient */}
            <div className="absolute top-0 left-0 right-0 h-32 bg-gradient-to-b from-red-500/20 to-transparent pointer-events-none" />

            <div className="relative p-8">
              <div className="flex items-start gap-4">
                <div className="flex-shrink-0 w-12 h-12 rounded-full bg-red-500/20 flex items-center justify-center">
                  <svg className="w-6 h-6 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                  </svg>
                </div>
                <div className="flex-1">
                  <h3 className="text-xl font-bold text-white mb-2">Delete Notebook</h3>
                  <p className="text-gray-400">
                    Are you sure you want to delete <span className="text-white font-medium">"{deleteConfirm.name}"</span>?
                  </p>
                  <p className="text-red-400 text-sm mt-2">
                    This action cannot be undone. All cells and chat history will be permanently deleted.
                  </p>
                </div>
              </div>

              <div className="flex gap-3 mt-6">
                <button
                  onClick={() => setDeleteConfirm(null)}
                  disabled={deleting}
                  className="flex-1 px-6 py-3 rounded-xl border border-white/10 text-gray-300 hover:bg-white/5 transition-all disabled:opacity-50"
                >
                  Cancel
                </button>
                <button
                  onClick={confirmDeleteProject}
                  disabled={deleting}
                  className="flex-1 px-6 py-3 rounded-xl bg-red-600 hover:bg-red-500 text-white font-medium shadow-lg shadow-red-500/25 disabled:opacity-50 transition-all flex items-center justify-center gap-2"
                >
                  {deleting ? (
                    <>
                      <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                      Deleting...
                    </>
                  ) : (
                    <>
                      <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                      </svg>
                      Delete Notebook
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Logs Viewer Modal */}
      {logsProject && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={handleCloseLogs} />
          <div className="relative w-[90vw] h-[85vh] rounded-2xl bg-slate-900 border border-white/10 shadow-2xl overflow-hidden flex flex-col">
            {/* Modal header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-white/10 bg-gradient-to-r from-gray-800 to-slate-800">
              <div className="flex items-center gap-3">
                <div className="w-10 h-10 rounded-xl bg-gray-700 flex items-center justify-center">
                  <svg className="w-5 h-5 text-gray-300" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                  </svg>
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-white">Container Logs</h3>
                  <p className="text-sm text-gray-400">{logsProject.name}</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <div className={`flex items-center gap-2 text-xs ${logsConnected ? 'text-emerald-400' : 'text-gray-400'}`}>
                  <div className={`w-2 h-2 rounded-full ${logsConnected ? 'bg-emerald-400 animate-pulse' : 'bg-gray-500'}`} />
                  {logsConnected ? 'Live' : 'Connecting...'}
                </div>
                <button
                  onClick={() => setLogs([])}
                  className="px-3 py-1.5 text-xs text-gray-400 hover:text-white hover:bg-white/10 rounded-lg transition-all"
                >
                  Clear
                </button>
                <button
                  onClick={handleCloseLogs}
                  className="p-2 text-gray-400 hover:text-white hover:bg-white/10 rounded-lg transition-all"
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                  </svg>
                </button>
              </div>
            </div>

            {/* Logs content */}
            <div className="flex-1 overflow-auto p-4 font-mono text-xs bg-black/80">
              {logs.length === 0 ? (
                <div className="flex items-center justify-center h-full text-gray-500">
                  Waiting for logs...
                </div>
              ) : (
                logs.map((line, i) => (
                  <div
                    key={i}
                    className={`${
                      line.includes('ERROR') || line.includes('error') ? 'text-red-400' :
                      line.includes('WARNING') || line.includes('warning') ? 'text-amber-400' :
                      line.includes('INFO') ? 'text-blue-400' :
                      'text-gray-300'
                    }`}
                  >
                    {line || '\u00A0'}
                  </div>
                ))
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
