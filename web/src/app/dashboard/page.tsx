'use client'

import { useEffect, useState, useCallback, useRef } from 'react'
import { useRouter } from 'next/navigation'
import { auth, projects, playgrounds, notebooks, workspaces } from '@/lib/api'
import { useAuthStore, useProjectsStore } from '@/lib/store'
import type { Project, Workspace } from '@/types'

// Apply dark theme on mount for dashboard
const useDashboardTheme = () => {
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', 'dark')
  }, [])
}

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
  useDashboardTheme()
  const router = useRouter()
  const { user, isLoading: authLoading, setUser } = useAuthStore()
  const { projects: projectList, setProjects, addProject, removeProject } = useProjectsStore()
  const [isLoading, setIsLoading] = useState(true)
  const [showNewProject, setShowNewProject] = useState(false)
  const [newProjectName, setNewProjectName] = useState('')
  const [newProjectDesc, setNewProjectDesc] = useState('')
  const [creating, setCreating] = useState(false)
  const [createError, setCreateError] = useState<string | null>(null)
  const [playgroundStatuses, setPlaygroundStatuses] = useState<PlaygroundStatus>({})
  const [notificationMessage, setNotificationMessage] = useState<string | null>(null)
  const [showImportModal, setShowImportModal] = useState(false)
  const [importProjectName, setImportProjectName] = useState('')
  const [importFile, setImportFile] = useState<File | null>(null)
  const [importing, setImporting] = useState(false)
  const [importError, setImportError] = useState<string | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const [editingProject, setEditingProject] = useState<Project | null>(null)
  const [editName, setEditName] = useState('')
  const [editDesc, setEditDesc] = useState('')
  const [editWorkspaceId, setEditWorkspaceId] = useState<string | null>(null)
  const [updating, setUpdating] = useState(false)
  const [deleteConfirm, setDeleteConfirm] = useState<Project | null>(null)
  const [deleting, setDeleting] = useState(false)
  const [downloadingProject, setDownloadingProject] = useState<string | null>(null)

  // Workspace state
  const [workspaceList, setWorkspaceList] = useState<Workspace[]>([])
  const [selectedWorkspaceId, setSelectedWorkspaceId] = useState<string | null>(null) // null = show first workspace
  const [showNewWorkspace, setShowNewWorkspace] = useState(false)
  const [newWorkspaceName, setNewWorkspaceName] = useState('')
  const [newWorkspaceColor, setNewWorkspaceColor] = useState('#3B82F6')
  const [creatingWorkspace, setCreatingWorkspace] = useState(false)
  const [editingWorkspace, setEditingWorkspace] = useState<Workspace | null>(null)
  const [editWorkspaceName, setEditWorkspaceName] = useState('')
  const [editWorkspaceColor, setEditWorkspaceColor] = useState('')
  const [updatingWorkspace, setUpdatingWorkspace] = useState(false)
  const [deleteWorkspaceConfirm, setDeleteWorkspaceConfirm] = useState<Workspace | null>(null)
  const [viewMode, setViewMode] = useState<'card' | 'list'>('list')

  // Workspace colors
  const workspaceColors = [
    { name: 'Blue', value: '#3B82F6' },
    { name: 'Purple', value: '#8B5CF6' },
    { name: 'Green', value: '#10B981' },
    { name: 'Amber', value: '#F59E0B' },
    { name: 'Red', value: '#EF4444' },
    { name: 'Pink', value: '#EC4899' },
    { name: 'Teal', value: '#14B8A6' },
    { name: 'Gray', value: '#6B7280' },
  ]

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

        const [{ projects: projectsData }, { workspaces: workspacesData }] = await Promise.all([
          projects.list(),
          workspaces.list(),
        ])

        setProjects(projectsData)
        setWorkspaceList(workspacesData)
        // Select first workspace by default
        if (workspacesData.length > 0) {
          setSelectedWorkspaceId(workspacesData[0].id)
        } else {
          setSelectedWorkspaceId('uncategorized')
        }
        projectsData.forEach((p: Project) => fetchPlaygroundStatus(p.id))
      } catch {
        router.push('/auth/login')
      } finally {
        setIsLoading(false)
      }
    }
    init()
  }, [router, setUser, setProjects, fetchPlaygroundStatus])

  // Poll playground statuses every 10 seconds to detect external changes (e.g., container killed)
  useEffect(() => {
    if (projectList.length === 0) return

    const pollStatuses = async () => {
      // Only poll for projects that are currently shown as running or starting
      const projectsToCheck = projectList.filter(p => {
        const status = playgroundStatuses[p.id]
        return status?.status === 'running' || status?.status === 'starting'
      })

      for (const project of projectsToCheck) {
        try {
          const pg = await playgrounds.get(project.id)
          const newStatus = pg?.status || 'stopped'
          const currentStatus = playgroundStatuses[project.id]?.status

          // Only update if status actually changed
          if (currentStatus !== newStatus) {
            setPlaygroundStatuses(prev => ({
              ...prev,
              [project.id]: {
                status: newStatus,
                loading: false,
                memory_limit_mb: pg?.memory_limit_mb,
                cpu_limit: pg?.cpu_limit,
              }
            }))
          }
        } catch {
          // If we can't fetch status, assume stopped
          if (playgroundStatuses[project.id]?.status !== 'stopped') {
            setPlaygroundStatuses(prev => ({
              ...prev,
              [project.id]: { status: 'stopped', loading: false }
            }))
          }
        }
      }
    }

    const interval = setInterval(pollStatuses, 10000) // Poll every 10 seconds
    return () => clearInterval(interval)
  }, [projectList, playgroundStatuses])

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
    setCreateError(null)
    try {
      const project = await projects.create({
        name: newProjectName.trim(),
        description: newProjectDesc.trim() || undefined,
        workspace_id: selectedWorkspaceId && selectedWorkspaceId !== 'uncategorized' ? selectedWorkspaceId : undefined,
      })
      addProject(project)
      setShowNewProject(false)
      setNewProjectName('')
      setNewProjectDesc('')

      // Refresh workspace counts
      const { workspaces: updatedWorkspaces } = await workspaces.list()
      setWorkspaceList(updatedWorkspaces)

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
    } catch (err: unknown) {
      console.error('Failed to create project:', err)
      // Extract error message from API response
      const axiosError = err as { response?: { data?: { detail?: string } } }
      const errorMessage = axiosError.response?.data?.detail || 'Failed to create project'
      setCreateError(errorMessage)
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
      // Refresh workspace counts
      const { workspaces: updatedWorkspaces } = await workspaces.list()
      setWorkspaceList(updatedWorkspaces)
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
      const name = file.name.replace(/\.ipynb$/i, '')
      setImportProjectName(name)
    }
  }

  const handleImportProject = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!importFile || !importProjectName.trim()) return

    setImporting(true)
    setImportError(null)
    try {
      const fileContent = await importFile.text()
      const ipynbData = JSON.parse(fileContent)

      const project = await projects.create({
        name: importProjectName.trim(),
        description: `Imported from ${importFile.name}`,
        workspace_id: selectedWorkspaceId && selectedWorkspaceId !== 'uncategorized' ? selectedWorkspaceId : undefined,
      })
      addProject(project)
      await notebooks.import(project.id, ipynbData)

      setShowImportModal(false)
      setImportFile(null)
      setImportProjectName('')
      if (fileInputRef.current) {
        fileInputRef.current.value = ''
      }

      // Refresh workspace counts
      const { workspaces: updatedWorkspaces } = await workspaces.list()
      setWorkspaceList(updatedWorkspaces)

      setNotificationMessage(`Successfully imported "${importFile.name}"`)
      setTimeout(() => setNotificationMessage(null), 5000)

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
    } catch (err: unknown) {
      console.error('Failed to import notebook:', err)
      // Extract error message from API response
      const axiosError = err as { response?: { data?: { detail?: string } } }
      const errorMessage = axiosError.response?.data?.detail || 'Failed to import notebook. Please check the file format.'
      setImportError(errorMessage)
    } finally {
      setImporting(false)
    }
  }

  const handleEditProject = (project: Project) => {
    setEditingProject(project)
    setEditName(project.name)
    setEditDesc(project.description || '')
    setEditWorkspaceId(project.workspace_id || null)
  }

  const handleUpdateProject = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editingProject || !editName.trim()) return

    setUpdating(true)
    try {
      const updated = await projects.update(editingProject.id, {
        name: editName.trim(),
        description: editDesc.trim() || undefined,
        workspace_id: editWorkspaceId || undefined,
      })
      // Update local state with workspace_id
      const updatedProject = { ...updated, workspace_id: editWorkspaceId || undefined }
      setProjects(projectList.map(p => p.id === updated.id ? updatedProject : p))
      setEditingProject(null)

      // Refresh workspace counts if workspace changed
      if (editingProject.workspace_id !== editWorkspaceId) {
        const { workspaces: updatedWorkspaces } = await workspaces.list()
        setWorkspaceList(updatedWorkspaces)
      }

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

  const handleViewLogs = (project: Project) => {
    // Open logs in new tab with xterm.js support
    window.open(`/logs/${project.id}`, '_blank')
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
    for (const project of projectList) {
      const status = playgroundStatuses[project.id]
      if (status?.status === 'running') {
        try {
          await playgrounds.stop(project.id)
        } catch {
          // Ignore errors
        }
      }
    }

    try { await auth.logout() } catch {}
    localStorage.removeItem('access_token')
    localStorage.removeItem('refresh_token')
    setUser(null)
    router.push('/auth/login')
  }

  // Workspace handlers
  const handleCreateWorkspace = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!newWorkspaceName.trim()) return
    setCreatingWorkspace(true)
    try {
      const workspace = await workspaces.create({
        name: newWorkspaceName.trim(),
        color: newWorkspaceColor,
      })
      setWorkspaceList(prev => [...prev, workspace])
      setShowNewWorkspace(false)
      setNewWorkspaceName('')
      setNewWorkspaceColor('#3B82F6')
      setSelectedWorkspaceId(workspace.id)
      setNotificationMessage('Workspace created successfully')
      setTimeout(() => setNotificationMessage(null), 3000)
    } catch (err) {
      console.error('Failed to create workspace:', err)
      setNotificationMessage('Failed to create workspace')
      setTimeout(() => setNotificationMessage(null), 3000)
    } finally {
      setCreatingWorkspace(false)
    }
  }

  const handleEditWorkspace = (workspace: Workspace) => {
    setEditingWorkspace(workspace)
    setEditWorkspaceName(workspace.name)
    setEditWorkspaceColor(workspace.color)
  }

  const handleUpdateWorkspace = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!editingWorkspace || !editWorkspaceName.trim()) return
    setUpdatingWorkspace(true)
    try {
      const updated = await workspaces.update(editingWorkspace.id, {
        name: editWorkspaceName.trim(),
        color: editWorkspaceColor,
      })
      setWorkspaceList(prev => prev.map(w => w.id === updated.id ? updated : w))
      setEditingWorkspace(null)
      setNotificationMessage('Workspace updated successfully')
      setTimeout(() => setNotificationMessage(null), 3000)
    } catch (err) {
      console.error('Failed to update workspace:', err)
      setNotificationMessage('Failed to update workspace')
      setTimeout(() => setNotificationMessage(null), 3000)
    } finally {
      setUpdatingWorkspace(false)
    }
  }

  const handleDeleteWorkspace = async () => {
    if (!deleteWorkspaceConfirm) return

    try {
      await workspaces.delete(deleteWorkspaceConfirm.id)
      setWorkspaceList(prev => prev.filter(w => w.id !== deleteWorkspaceConfirm.id))
      setProjects(projectList.filter(p => p.workspace_id !== deleteWorkspaceConfirm.id))
      if (selectedWorkspaceId === deleteWorkspaceConfirm.id) {
        const remaining = workspaceList.filter(w => w.id !== deleteWorkspaceConfirm.id)
        setSelectedWorkspaceId(remaining.length > 0 ? remaining[0].id : 'uncategorized')
      }
      setDeleteWorkspaceConfirm(null)
      setEditingWorkspace(null)
      setNotificationMessage('Workspace deleted successfully')
      setTimeout(() => setNotificationMessage(null), 3000)
    } catch (err) {
      console.error('Failed to delete workspace:', err)
      setNotificationMessage('Failed to delete workspace')
      setTimeout(() => setNotificationMessage(null), 3000)
    }
  }

  // Filter projects based on selected workspace
  const getFilteredProjects = () => {
    if (selectedWorkspaceId === 'uncategorized') {
      return projectList.filter(p => !p.workspace_id)
    }
    if (selectedWorkspaceId) {
      return projectList.filter(p => p.workspace_id === selectedWorkspaceId)
    }
    return projectList
  }

  const getSelectedWorkspace = () => {
    if (!selectedWorkspaceId || selectedWorkspaceId === 'uncategorized') return null
    return workspaceList.find(w => w.id === selectedWorkspaceId)
  }

  const getSelectedWorkspaceName = () => {
    if (selectedWorkspaceId === 'uncategorized') return 'Uncategorized'
    const workspace = workspaceList.find(w => w.id === selectedWorkspaceId)
    return workspace?.name || 'Select a Workspace'
  }

  const uncategorizedCount = projectList.filter(p => !p.workspace_id).length
  const activePlaygrounds = Object.values(playgroundStatuses).filter(s => s.status === 'running').length

  if (isLoading || authLoading) {
    return (
      <div
        className="min-h-screen flex items-center justify-center"
        style={{ backgroundColor: 'var(--app-bg-primary)' }}
      >
        <div className="flex flex-col items-center gap-4">
          <div
            className="w-12 h-12 border-4 rounded-full animate-spin"
            style={{
              borderColor: 'rgba(59, 130, 246, 0.3)',
              borderTopColor: 'var(--app-accent-primary)'
            }}
          />
          <span style={{ color: 'var(--app-accent-primary)' }} className="text-sm">
            Loading your workspace...
          </span>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen" style={{ backgroundColor: 'var(--app-bg-primary)' }}>
      {/* Notification Banner */}
      {notificationMessage && (
        <div className="fixed top-4 left-1/2 -translate-x-1/2 z-50 max-w-lg w-full mx-4 animate-in slide-in-from-top duration-300">
          <div
            className="backdrop-blur-xl rounded-xl p-4 flex items-start gap-3 shadow-lg"
            style={{
              backgroundColor: 'rgba(16, 185, 129, 0.15)',
              border: '1px solid rgba(16, 185, 129, 0.3)'
            }}
          >
            <div
              className="flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center"
              style={{ backgroundColor: 'rgba(16, 185, 129, 0.3)' }}
            >
              <svg className="w-5 h-5" style={{ color: 'var(--app-accent-success)' }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <div className="flex-1">
              <p className="text-sm" style={{ color: 'var(--app-accent-success)' }}>{notificationMessage}</p>
            </div>
            <button
              onClick={() => setNotificationMessage(null)}
              className="flex-shrink-0 transition-colors hover:opacity-80"
              style={{ color: 'var(--app-accent-success)' }}
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
        <div
          className="absolute -top-40 -right-40 w-80 h-80 rounded-full mix-blend-multiply filter blur-3xl opacity-20"
          style={{ backgroundColor: 'var(--app-accent-primary)' }}
        />
        <div
          className="absolute -bottom-40 -left-40 w-80 h-80 rounded-full mix-blend-multiply filter blur-3xl opacity-20"
          style={{ backgroundColor: 'var(--app-accent-secondary)' }}
        />
      </div>

      {/* Header */}
      <header
        className="relative z-10 backdrop-blur-xl"
        style={{
          backgroundColor: 'var(--app-bg-secondary)',
          borderBottom: '1px solid var(--app-border-default)'
        }}
      >
        <div className="max-w-7xl mx-auto px-6 py-4">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-3">
              <div
                className="w-10 h-10 rounded-xl flex items-center justify-center shadow-lg"
                style={{
                  background: 'var(--app-gradient-primary)',
                  boxShadow: '0 10px 40px rgba(59, 130, 246, 0.3)'
                }}
              >
                <svg className="w-6 h-6 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                </svg>
              </div>
              <div>
                <h1 className="text-xl font-bold" style={{ color: 'var(--app-text-primary)' }}>AI Notebook</h1>
                <p className="text-xs" style={{ color: 'var(--app-accent-primary)' }}>Intelligent Computing Environment</p>
              </div>
            </div>
            <div className="flex items-center gap-6">
              <div
                className="flex items-center gap-2 px-4 py-2 rounded-full"
                style={{
                  backgroundColor: 'var(--app-bg-card)',
                  border: '1px solid var(--app-border-default)'
                }}
              >
                <div className="w-2 h-2 rounded-full animate-pulse" style={{ backgroundColor: 'var(--app-accent-success)' }} />
                <span className="text-sm" style={{ color: 'var(--app-text-secondary)' }}>{user?.email}</span>
              </div>
              <button
                onClick={handleLogout}
                className="px-4 py-2 text-sm transition-colors hover:opacity-80"
                style={{ color: 'var(--app-text-muted)' }}
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
        <div className="mb-8">
          <div className="flex justify-between items-end">
            <div>
              <h2 className="text-4xl font-bold mb-2" style={{ color: 'var(--app-text-primary)' }}>
                Welcome back<span style={{ color: 'var(--app-accent-primary)' }}>.</span>
              </h2>
              <p className="text-lg" style={{ color: 'var(--app-text-muted)' }}>
                Create, explore, and run AI-powered notebooks
              </p>
            </div>
            <div className="flex items-center gap-3">
              <button
                onClick={() => setShowImportModal(true)}
                className="group px-5 py-3 rounded-xl font-medium transition-all duration-300 flex items-center gap-2 hover:opacity-90"
                style={{
                  backgroundColor: 'var(--app-bg-card)',
                  color: 'var(--app-text-primary)',
                  border: '1px solid var(--app-border-default)'
                }}
              >
                <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                </svg>
                Import .ipynb
              </button>
              <button
                onClick={() => setShowNewProject(true)}
                className="group px-6 py-3 text-white rounded-xl font-medium shadow-lg transition-all duration-300 flex items-center gap-2 hover:opacity-90"
                style={{
                  background: 'var(--app-gradient-primary)',
                  boxShadow: '0 4px 20px rgba(59, 130, 246, 0.3)'
                }}
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
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-8">
          <div
            className="p-6 rounded-2xl backdrop-blur-sm"
            style={{
              backgroundColor: 'var(--app-bg-card)',
              border: '1px solid var(--app-border-default)'
            }}
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm" style={{ color: 'var(--app-text-muted)' }}>Total Notebooks</p>
                <p className="text-3xl font-bold mt-1" style={{ color: 'var(--app-text-primary)' }}>{projectList.length}</p>
              </div>
              <div
                className="w-12 h-12 rounded-xl flex items-center justify-center"
                style={{ backgroundColor: 'rgba(59, 130, 246, 0.2)' }}
              >
                <svg className="w-6 h-6" style={{ color: 'var(--app-accent-primary)' }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                </svg>
              </div>
            </div>
          </div>
          <div
            className="p-6 rounded-2xl backdrop-blur-sm"
            style={{
              backgroundColor: 'var(--app-bg-card)',
              border: '1px solid var(--app-border-default)'
            }}
          >
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm" style={{ color: 'var(--app-text-muted)' }}>Active Playgrounds</p>
                <p className="text-3xl font-bold mt-1" style={{ color: 'var(--app-text-primary)' }}>{activePlaygrounds}</p>
              </div>
              <div
                className="w-12 h-12 rounded-xl flex items-center justify-center"
                style={{ backgroundColor: 'rgba(16, 185, 129, 0.2)' }}
              >
                <svg className="w-6 h-6" style={{ color: 'var(--app-accent-success)' }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 3v4M3 5h4M6 17v4m-2-2h4m5-16l2.286 6.857L21 12l-5.714 2.143L13 21l-2.286-6.857L5 12l5.714-2.143L13 3z" />
                </svg>
              </div>
            </div>
          </div>
        </div>

        {/* Workspace Sidebar + Projects Grid */}
        <div className="flex gap-6">
          {/* Workspace Sidebar */}
          <div className="w-64 flex-shrink-0">
            <div
              className="sticky top-24 rounded-2xl backdrop-blur-sm overflow-hidden"
              style={{
                backgroundColor: 'var(--app-bg-card)',
                border: '1px solid var(--app-border-default)'
              }}
            >
              <div className="p-4" style={{ borderBottom: '1px solid var(--app-border-default)' }}>
                <h3 className="text-sm font-semibold uppercase tracking-wider" style={{ color: 'var(--app-text-primary)' }}>Workspaces</h3>
              </div>
              <div className="p-2 max-h-[60vh] overflow-y-auto">
                {/* Workspace Items */}
                {workspaceList.map(ws => (
                  <div
                    key={ws.id}
                    className="group flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all mb-1 cursor-pointer"
                    style={{
                      backgroundColor: selectedWorkspaceId === ws.id ? 'var(--app-bg-input)' : 'transparent',
                      color: selectedWorkspaceId === ws.id ? 'var(--app-text-primary)' : 'var(--app-text-muted)'
                    }}
                    onClick={() => setSelectedWorkspaceId(ws.id)}
                  >
                    <div
                      className="w-3 h-3 rounded-full flex-shrink-0"
                      style={{ backgroundColor: ws.color }}
                    />
                    <span className="flex-1 text-sm truncate">{ws.name}</span>
                    <button
                      onClick={(e) => { e.stopPropagation(); handleEditWorkspace(ws) }}
                      className="p-1 opacity-0 group-hover:opacity-100 transition-all"
                      style={{ color: 'var(--app-text-muted)' }}
                      title="Edit workspace"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                      </svg>
                    </button>
                    <span
                      className="text-xs px-2 py-0.5 rounded-full"
                      style={{ backgroundColor: 'var(--app-bg-input)' }}
                    >{ws.project_count}</span>
                  </div>
                ))}

                {/* Uncategorized */}
                {uncategorizedCount > 0 && (
                  <button
                    onClick={() => setSelectedWorkspaceId('uncategorized')}
                    className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all mb-1"
                    style={{
                      backgroundColor: selectedWorkspaceId === 'uncategorized' ? 'var(--app-bg-input)' : 'transparent',
                      color: selectedWorkspaceId === 'uncategorized' ? 'var(--app-text-primary)' : 'var(--app-text-muted)'
                    }}
                  >
                    <div className="w-3 h-3 rounded-full flex-shrink-0" style={{ backgroundColor: 'var(--app-text-muted)' }} />
                    <span className="flex-1 text-left text-sm">Uncategorized</span>
                    <span
                      className="text-xs px-2 py-0.5 rounded-full"
                      style={{ backgroundColor: 'var(--app-bg-input)' }}
                    >{uncategorizedCount}</span>
                  </button>
                )}

                {/* New Workspace Button */}
                <button
                  onClick={() => setShowNewWorkspace(true)}
                  className="w-full flex items-center gap-3 px-3 py-2.5 rounded-xl transition-all mt-2"
                  style={{
                    color: 'var(--app-text-muted)',
                    border: '1px dashed var(--app-border-default)'
                  }}
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                  </svg>
                  <span className="text-sm">New Workspace</span>
                </button>
              </div>
            </div>
          </div>

          {/* Projects Grid */}
          <div className="flex-1">
            {/* Workspace Header */}
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-3">
                {getSelectedWorkspace() && (
                  <div
                    className="w-4 h-4 rounded-full"
                    style={{ backgroundColor: getSelectedWorkspace()?.color }}
                  />
                )}
                <h3 className="text-xl font-semibold" style={{ color: 'var(--app-text-primary)' }}>{getSelectedWorkspaceName()}</h3>
                <span className="text-sm" style={{ color: 'var(--app-text-muted)' }}>
                  {getFilteredProjects().length} notebook{getFilteredProjects().length !== 1 ? 's' : ''}
                </span>
              </div>
              {/* View Toggle */}
              <div
                className="flex items-center gap-1 p-1 rounded-lg"
                style={{
                  backgroundColor: 'var(--app-bg-card)',
                  border: '1px solid var(--app-border-default)'
                }}
              >
                <button
                  onClick={() => setViewMode('card')}
                  className="p-2 rounded-md transition-all"
                  style={{
                    backgroundColor: viewMode === 'card' ? 'var(--app-bg-input)' : 'transparent',
                    color: viewMode === 'card' ? 'var(--app-text-primary)' : 'var(--app-text-muted)'
                  }}
                  title="Card view"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zM14 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zM14 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z" />
                  </svg>
                </button>
                <button
                  onClick={() => setViewMode('list')}
                  className="p-2 rounded-md transition-all"
                  style={{
                    backgroundColor: viewMode === 'list' ? 'var(--app-bg-input)' : 'transparent',
                    color: viewMode === 'list' ? 'var(--app-text-primary)' : 'var(--app-text-muted)'
                  }}
                  title="List view"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 10h16M4 14h16M4 18h16" />
                  </svg>
                </button>
              </div>
            </div>

            {getFilteredProjects().length === 0 ? (
              <div
                className="text-center py-16 rounded-2xl"
                style={{
                  backgroundColor: 'var(--app-bg-card)',
                  border: '1px solid var(--app-border-default)'
                }}
              >
                <div
                  className="w-16 h-16 mx-auto mb-4 rounded-2xl flex items-center justify-center"
                  style={{
                    backgroundColor: 'var(--app-bg-card)',
                    border: '1px solid var(--app-border-default)'
                  }}
                >
                  <svg className="w-8 h-8" style={{ color: 'var(--app-text-muted)' }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                  </svg>
                </div>
                <h4 className="text-lg font-medium mb-2" style={{ color: 'var(--app-text-primary)' }}>No notebooks here</h4>
                <p className="mb-4 text-sm" style={{ color: 'var(--app-text-muted)' }}>Create a notebook in this workspace</p>
                <button
                  onClick={() => setShowNewProject(true)}
                  className="px-5 py-2.5 text-white rounded-xl font-medium text-sm shadow-lg"
                  style={{
                    background: 'var(--app-gradient-primary)',
                    boxShadow: '0 4px 20px rgba(59, 130, 246, 0.3)'
                  }}
                >
                  Create Notebook
                </button>
              </div>
            ) : viewMode === 'card' ? (
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-5">
                {getFilteredProjects().map((project) => {
                  const pgStatus = playgroundStatuses[project.id] || { status: 'stopped', loading: false }
                  const isRunning = pgStatus.status === 'running'
                  const isLoading = pgStatus.loading
                  const projectWorkspace = workspaceList.find(w => w.id === project.workspace_id)

                  return (
                    <div
                      key={project.id}
                      className="group relative rounded-2xl backdrop-blur-sm overflow-hidden transition-all duration-300"
                      style={{
                        backgroundColor: 'var(--app-bg-card)',
                        border: '1px solid var(--app-border-default)'
                      }}
                    >
                      {/* Workspace color bar */}
                      <div
                        className="absolute top-0 left-0 right-0 h-1"
                        style={{ backgroundColor: projectWorkspace?.color || '#6B7280' }}
                      />

                      <div className="p-5">
                        {/* Header */}
                        <div className="flex items-start justify-between mb-3">
                          <div className="flex items-center gap-3 min-w-0">
                            <div
                              className="w-10 h-10 rounded-xl flex items-center justify-center"
                              style={{
                                background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.2), rgba(20, 184, 166, 0.2))',
                                border: '1px solid var(--app-border-default)',
                                color: 'var(--app-accent-secondary)'
                              }}
                            >
                              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                              </svg>
                            </div>
                            <div className="min-w-0">
                              <h4 className="font-semibold truncate" style={{ color: 'var(--app-text-primary)' }}>{project.name}</h4>
                              <p className="text-xs" style={{ color: 'var(--app-text-muted)' }}>{new Date(project.updated_at).toLocaleDateString()}</p>
                            </div>
                          </div>
                          <div className="flex gap-1 opacity-0 group-hover:opacity-100 transition-all">
                            <button
                              onClick={() => handleDownloadProject(project)}
                              disabled={downloadingProject === project.id}
                              className="p-1.5 rounded-lg transition-all disabled:opacity-50"
                              style={{ color: 'var(--app-text-muted)' }}
                              title="Download"
                            >
                              {downloadingProject === project.id ? (
                                <div className="w-4 h-4 border-2 rounded-full animate-spin" style={{ borderColor: 'rgba(20, 184, 166, 0.3)', borderTopColor: 'var(--app-accent-secondary)' }} />
                              ) : (
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                                </svg>
                              )}
                            </button>
                            <button
                              onClick={() => handleEditProject(project)}
                              className="p-1.5 rounded-lg transition-all"
                              style={{ color: 'var(--app-text-muted)' }}
                              title="Edit"
                            >
                              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                              </svg>
                            </button>
                            <button
                              onClick={() => handleDeleteProject(project)}
                              className="p-1.5 rounded-lg transition-all"
                              style={{ color: 'var(--app-accent-error)' }}
                              title="Delete"
                            >
                              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                              </svg>
                            </button>
                          </div>
                        </div>

                        {/* Description */}
                        {project.description && (
                          <p className="text-sm mb-3 line-clamp-2" style={{ color: 'var(--app-text-muted)' }}>{project.description}</p>
                        )}

                        {/* Status */}
                        <div className="flex items-center gap-2 mb-3">
                          <div
                            className={`w-2 h-2 rounded-full ${
                              pgStatus.status === 'starting' || pgStatus.status === 'stopping' ? 'animate-pulse' : ''
                            }`}
                            style={{
                              backgroundColor: pgStatus.status === 'running' ? 'var(--app-accent-success)' :
                                pgStatus.status === 'starting' || pgStatus.status === 'stopping' ? 'var(--app-accent-warning)' :
                                pgStatus.status === 'error' ? 'var(--app-accent-error)' : 'var(--app-text-muted)',
                              boxShadow: pgStatus.status === 'running' ? '0 0 8px rgba(16, 185, 129, 0.5)' : 'none'
                            }}
                          />
                          <span className="text-xs" style={{ color: 'var(--app-text-muted)' }}>
                            {pgStatus.status === 'running' ? 'Running' :
                             pgStatus.status === 'starting' ? 'Starting...' :
                             pgStatus.status === 'stopping' ? 'Stopping...' :
                             pgStatus.status === 'error' ? 'Error' : 'Stopped'}
                          </span>
                        </div>

                        {/* Controls */}
                        <div className="flex gap-2 mb-3">
                          {!isRunning ? (
                            <button
                              onClick={() => handleStartPlayground(project.id)}
                              disabled={isLoading}
                              className="flex-1 px-3 py-2 text-sm rounded-xl transition-all disabled:opacity-50 flex items-center justify-center gap-2"
                              style={{
                                backgroundColor: 'rgba(16, 185, 129, 0.2)',
                                color: 'var(--app-accent-success)',
                                border: '1px solid rgba(16, 185, 129, 0.3)'
                              }}
                            >
                              {isLoading ? (
                                <div className="w-4 h-4 border-2 rounded-full animate-spin" style={{ borderColor: 'rgba(16, 185, 129, 0.3)', borderTopColor: 'var(--app-accent-success)' }} />
                              ) : (
                                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                                </svg>
                              )}
                              Start
                            </button>
                          ) : (
                            <>
                              <button
                                onClick={() => handleStopPlayground(project.id)}
                                disabled={isLoading}
                                className="flex-1 px-3 py-2 text-sm rounded-xl transition-all disabled:opacity-50"
                                style={{
                                  backgroundColor: 'rgba(239, 68, 68, 0.2)',
                                  color: 'var(--app-accent-error)',
                                  border: '1px solid rgba(239, 68, 68, 0.3)'
                                }}
                              >
                                Stop
                              </button>
                              <button
                                onClick={() => handleRestartPlayground(project.id)}
                                disabled={isLoading}
                                className="flex-1 px-3 py-2 text-sm rounded-xl transition-all disabled:opacity-50"
                                style={{
                                  backgroundColor: 'rgba(245, 158, 11, 0.2)',
                                  color: 'var(--app-accent-warning)',
                                  border: '1px solid rgba(245, 158, 11, 0.3)'
                                }}
                              >
                                Restart
                              </button>
                              <button
                                onClick={() => handleViewLogs(project)}
                                className="flex-1 px-3 py-2 text-sm rounded-xl transition-all"
                                style={{
                                  backgroundColor: 'rgba(59, 130, 246, 0.2)',
                                  color: 'var(--app-accent-primary)',
                                  border: '1px solid rgba(59, 130, 246, 0.3)'
                                }}
                              >
                                Logs
                              </button>
                            </>
                          )}
                        </div>

                        {/* Open Button */}
                        <button
                          onClick={() => router.push(`/notebook/${project.id}`)}
                          disabled={!isRunning}
                          className="w-full py-2.5 rounded-xl font-medium text-sm transition-all flex items-center justify-center gap-2"
                          style={isRunning ? {
                            background: 'var(--app-gradient-primary)',
                            color: 'white',
                            boxShadow: '0 4px 20px rgba(59, 130, 246, 0.3)'
                          } : {
                            backgroundColor: 'var(--app-bg-card)',
                            color: 'var(--app-text-muted)',
                            border: '1px solid var(--app-border-default)',
                            cursor: 'not-allowed'
                          }}
                        >
                          {isRunning ? 'Open Notebook' : 'Start to Open'}
                        </button>
                      </div>
                    </div>
                  )
                })}
              </div>
            ) : (
              /* List View */
              <div
                className="rounded-2xl backdrop-blur-sm overflow-hidden"
                style={{
                  backgroundColor: 'var(--app-bg-card)',
                  border: '1px solid var(--app-border-default)'
                }}
              >
                {/* List Header */}
                <div
                  className="grid grid-cols-12 gap-4 px-4 py-3 text-xs font-medium uppercase tracking-wider"
                  style={{
                    borderBottom: '1px solid var(--app-border-default)',
                    color: 'var(--app-text-muted)'
                  }}
                >
                  <div className="col-span-4">Name</div>
                  <div className="col-span-2">Status</div>
                  <div className="col-span-2">Updated</div>
                  <div className="col-span-4 text-right">Actions</div>
                </div>
                {/* List Items */}
                {getFilteredProjects().map((project) => {
                  const pgStatus = playgroundStatuses[project.id] || { status: 'stopped', loading: false }
                  const isRunning = pgStatus.status === 'running'
                  const isLoading = pgStatus.loading
                  const projectWorkspace = workspaceList.find(w => w.id === project.workspace_id)

                  return (
                    <div
                      key={project.id}
                      className="group grid grid-cols-12 gap-4 px-4 py-3 transition-all items-center"
                      style={{ borderBottom: '1px solid var(--app-border-subtle)' }}
                    >
                      {/* Name */}
                      <div className="col-span-4 flex items-center gap-3 min-w-0">
                        <div
                          className="w-1 h-8 rounded-full flex-shrink-0"
                          style={{ backgroundColor: projectWorkspace?.color || '#6B7280' }}
                        />
                        <div
                          className="w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0"
                          style={{
                            background: 'linear-gradient(135deg, rgba(59, 130, 246, 0.2), rgba(20, 184, 166, 0.2))',
                            border: '1px solid var(--app-border-default)',
                            color: 'var(--app-accent-secondary)'
                          }}
                        >
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6.253v13m0-13C10.832 5.477 9.246 5 7.5 5S4.168 5.477 3 6.253v13C4.168 18.477 5.754 18 7.5 18s3.332.477 4.5 1.253m0-13C13.168 5.477 14.754 5 16.5 5c1.747 0 3.332.477 4.5 1.253v13C19.832 18.477 18.247 18 16.5 18c-1.746 0-3.332.477-4.5 1.253" />
                          </svg>
                        </div>
                        <div className="min-w-0">
                          <h4 className="font-medium truncate text-sm" style={{ color: 'var(--app-text-primary)' }}>{project.name}</h4>
                          {project.description && (
                            <p className="text-xs truncate" style={{ color: 'var(--app-text-muted)' }}>{project.description}</p>
                          )}
                        </div>
                      </div>

                      {/* Status */}
                      <div className="col-span-2">
                        <div className="flex items-center gap-2">
                          <div
                            className={`w-2 h-2 rounded-full ${
                              pgStatus.status === 'starting' || pgStatus.status === 'stopping' ? 'animate-pulse' : ''
                            }`}
                            style={{
                              backgroundColor: pgStatus.status === 'running' ? 'var(--app-accent-success)' :
                                pgStatus.status === 'starting' || pgStatus.status === 'stopping' ? 'var(--app-accent-warning)' :
                                pgStatus.status === 'error' ? 'var(--app-accent-error)' : 'var(--app-text-muted)',
                              boxShadow: pgStatus.status === 'running' ? '0 0 8px rgba(16, 185, 129, 0.5)' : 'none'
                            }}
                          />
                          <span
                            className="text-xs"
                            style={{
                              color: pgStatus.status === 'running' ? 'var(--app-accent-success)' :
                                pgStatus.status === 'starting' || pgStatus.status === 'stopping' ? 'var(--app-accent-warning)' :
                                pgStatus.status === 'error' ? 'var(--app-accent-error)' : 'var(--app-text-muted)'
                            }}
                          >
                            {pgStatus.status === 'running' ? 'Running' :
                             pgStatus.status === 'starting' ? 'Starting...' :
                             pgStatus.status === 'stopping' ? 'Stopping...' :
                             pgStatus.status === 'error' ? 'Error' : 'Stopped'}
                          </span>
                        </div>
                      </div>

                      {/* Updated */}
                      <div className="col-span-2 text-sm" style={{ color: 'var(--app-text-muted)' }}>
                        {new Date(project.updated_at).toLocaleDateString()}
                      </div>

                      {/* Actions */}
                      <div className="col-span-4 flex items-center justify-end gap-2">
                        {/* Playground Controls */}
                        {!isRunning ? (
                          <button
                            onClick={() => handleStartPlayground(project.id)}
                            disabled={isLoading}
                            className="px-3 py-1.5 text-xs rounded-lg transition-all disabled:opacity-50 flex items-center gap-1.5"
                            style={{
                              backgroundColor: 'rgba(16, 185, 129, 0.2)',
                              color: 'var(--app-accent-success)',
                              border: '1px solid rgba(16, 185, 129, 0.3)'
                            }}
                          >
                            {isLoading ? (
                              <div className="w-3 h-3 border-2 rounded-full animate-spin" style={{ borderColor: 'rgba(16, 185, 129, 0.3)', borderTopColor: 'var(--app-accent-success)' }} />
                            ) : (
                              <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                              </svg>
                            )}
                            Start
                          </button>
                        ) : (
                          <>
                            <button
                              onClick={() => handleStopPlayground(project.id)}
                              disabled={isLoading}
                              className="px-2 py-1.5 text-xs rounded-lg transition-all disabled:opacity-50"
                              style={{
                                backgroundColor: 'rgba(239, 68, 68, 0.2)',
                                color: 'var(--app-accent-error)',
                                border: '1px solid rgba(239, 68, 68, 0.3)'
                              }}
                              title="Stop"
                            >
                              Stop
                            </button>
                            <button
                              onClick={() => handleViewLogs(project)}
                              className="px-2 py-1.5 text-xs rounded-lg transition-all"
                              style={{
                                backgroundColor: 'rgba(59, 130, 246, 0.2)',
                                color: 'var(--app-accent-primary)',
                                border: '1px solid rgba(59, 130, 246, 0.3)'
                              }}
                              title="Logs"
                            >
                              Logs
                            </button>
                            <button
                              onClick={() => router.push(`/notebook/${project.id}`)}
                              className="px-3 py-1.5 text-xs text-white rounded-lg transition-all shadow-lg"
                              style={{
                                background: 'var(--app-gradient-primary)',
                                boxShadow: '0 4px 20px rgba(59, 130, 246, 0.3)'
                              }}
                            >
                              Open
                            </button>
                          </>
                        )}

                        {/* More Actions */}
                        <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-all">
                          <button
                            onClick={() => handleDownloadProject(project)}
                            disabled={downloadingProject === project.id}
                            className="p-1.5 rounded-lg transition-all disabled:opacity-50"
                            style={{ color: 'var(--app-text-muted)' }}
                            title="Download"
                          >
                            {downloadingProject === project.id ? (
                              <div className="w-4 h-4 border-2 rounded-full animate-spin" style={{ borderColor: 'rgba(20, 184, 166, 0.3)', borderTopColor: 'var(--app-accent-secondary)' }} />
                            ) : (
                              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                              </svg>
                            )}
                          </button>
                          <button
                            onClick={() => handleEditProject(project)}
                            className="p-1.5 rounded-lg transition-all"
                            style={{ color: 'var(--app-text-muted)' }}
                            title="Edit"
                          >
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
                            </svg>
                          </button>
                          <button
                            onClick={() => handleDeleteProject(project)}
                            className="p-1.5 rounded-lg transition-all"
                            style={{ color: 'var(--app-accent-error)' }}
                            title="Delete"
                          >
                            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                            </svg>
                          </button>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        </div>
      </main>

      {/* New Project Modal */}
      {showNewProject && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setShowNewProject(false)} />
          <div
            className="relative w-full max-w-md rounded-2xl shadow-2xl p-6"
            style={{
              backgroundColor: 'var(--app-bg-secondary)',
              border: '1px solid var(--app-border-default)'
            }}
          >
            <h3 className="text-xl font-bold mb-4" style={{ color: 'var(--app-text-primary)' }}>New Notebook</h3>
            <form onSubmit={handleCreateProject} className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-2" style={{ color: 'var(--app-text-secondary)' }}>Name</label>
                <input
                  type="text"
                  value={newProjectName}
                  onChange={(e) => setNewProjectName(e.target.value)}
                  className="w-full px-4 py-3 rounded-xl focus:outline-none"
                  style={{
                    backgroundColor: 'var(--app-bg-input)',
                    border: '1px solid var(--app-border-default)',
                    color: 'var(--app-text-primary)'
                  }}
                  placeholder="My Notebook"
                  required
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-2" style={{ color: 'var(--app-text-secondary)' }}>Description (optional)</label>
                <textarea
                  value={newProjectDesc}
                  onChange={(e) => setNewProjectDesc(e.target.value)}
                  className="w-full px-4 py-3 rounded-xl focus:outline-none resize-none"
                  style={{
                    backgroundColor: 'var(--app-bg-input)',
                    border: '1px solid var(--app-border-default)',
                    color: 'var(--app-text-primary)'
                  }}
                  placeholder="What's this notebook about?"
                  rows={2}
                />
              </div>
              {selectedWorkspaceId && selectedWorkspaceId !== 'uncategorized' && (
                <p className="text-sm" style={{ color: 'var(--app-text-muted)' }}>
                  Will be created in: <span style={{ color: 'var(--app-text-primary)' }}>{getSelectedWorkspaceName()}</span>
                </p>
              )}
              {createError && (
                <div className="p-3 rounded-xl" style={{ backgroundColor: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.3)' }}>
                  <p className="text-sm" style={{ color: 'var(--app-accent-error)' }}>{createError}</p>
                </div>
              )}
              <div className="flex gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => { setShowNewProject(false); setCreateError(null) }}
                  className="flex-1 px-4 py-2.5 rounded-xl"
                  style={{ border: '1px solid var(--app-border-default)', color: 'var(--app-text-secondary)' }}
                >Cancel</button>
                <button
                  type="submit"
                  disabled={creating}
                  className="flex-1 px-4 py-2.5 rounded-xl text-white font-medium disabled:opacity-50 flex items-center justify-center gap-2"
                  style={{ background: 'var(--app-gradient-primary)' }}
                >
                  {creating && <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />}
                  Create
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Import Modal */}
      {showImportModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setShowImportModal(false)} />
          <div
            className="relative w-full max-w-md rounded-2xl shadow-2xl p-6"
            style={{ backgroundColor: 'var(--app-bg-secondary)', border: '1px solid var(--app-border-default)' }}
          >
            <h3 className="text-xl font-bold mb-4" style={{ color: 'var(--app-text-primary)' }}>Import Notebook</h3>
            <form onSubmit={handleImportProject} className="space-y-4">
              <div
                onClick={() => fileInputRef.current?.click()}
                className="p-6 rounded-xl border-2 border-dashed cursor-pointer transition-all"
                style={{
                  borderColor: importFile ? 'var(--app-accent-primary)' : 'var(--app-border-default)',
                  backgroundColor: importFile ? 'rgba(59, 130, 246, 0.1)' : 'var(--app-bg-card)'
                }}
              >
                <input ref={fileInputRef} type="file" accept=".ipynb" onChange={handleFileSelect} className="hidden" />
                <div className="text-center">
                  {importFile ? (
                    <>
                      <svg className="w-8 h-8 mx-auto mb-2" style={{ color: 'var(--app-accent-primary)' }} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" /></svg>
                      <p className="font-medium" style={{ color: 'var(--app-accent-primary)' }}>{importFile.name}</p>
                    </>
                  ) : (
                    <>
                      <svg className="w-8 h-8 mx-auto mb-2" style={{ color: 'var(--app-text-muted)' }} fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" /></svg>
                      <p style={{ color: 'var(--app-text-muted)' }}>Click to select .ipynb file</p>
                    </>
                  )}
                </div>
              </div>
              <div>
                <label className="block text-sm font-medium mb-2" style={{ color: 'var(--app-text-secondary)' }}>Notebook Name</label>
                <input
                  type="text"
                  value={importProjectName}
                  onChange={(e) => setImportProjectName(e.target.value)}
                  className="w-full px-4 py-3 rounded-xl focus:outline-none"
                  style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }}
                  placeholder="Notebook name"
                  required
                />
              </div>
              {importError && (
                <div className="p-3 rounded-xl" style={{ backgroundColor: 'rgba(239, 68, 68, 0.15)', border: '1px solid rgba(239, 68, 68, 0.3)' }}>
                  <p className="text-sm" style={{ color: 'var(--app-accent-error)' }}>{importError}</p>
                </div>
              )}
              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => { setShowImportModal(false); setImportFile(null); setImportProjectName(''); setImportError(null) }} className="flex-1 px-4 py-2.5 rounded-xl" style={{ border: '1px solid var(--app-border-default)', color: 'var(--app-text-secondary)' }}>Cancel</button>
                <button type="submit" disabled={importing || !importFile} className="flex-1 px-4 py-2.5 rounded-xl text-white font-medium disabled:opacity-50 flex items-center justify-center gap-2" style={{ background: 'var(--app-gradient-primary)' }}>
                  {importing && <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />}
                  Import
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Project Modal */}
      {editingProject && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setEditingProject(null)} />
          <div className="relative w-full max-w-md rounded-2xl shadow-2xl p-6" style={{ backgroundColor: 'var(--app-bg-secondary)', border: '1px solid var(--app-border-default)' }}>
            <h3 className="text-xl font-bold mb-4" style={{ color: 'var(--app-text-primary)' }}>Edit Notebook</h3>
            <form onSubmit={handleUpdateProject} className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-2" style={{ color: 'var(--app-text-secondary)' }}>Name</label>
                <input type="text" value={editName} onChange={(e) => setEditName(e.target.value)} className="w-full px-4 py-3 rounded-xl focus:outline-none" style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }} required />
              </div>
              <div>
                <label className="block text-sm font-medium mb-2" style={{ color: 'var(--app-text-secondary)' }}>Description</label>
                <textarea value={editDesc} onChange={(e) => setEditDesc(e.target.value)} className="w-full px-4 py-3 rounded-xl focus:outline-none resize-none" style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }} rows={2} />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1" style={{ color: 'var(--app-text-secondary)' }}>Workspace</label>
                <p className="text-xs mb-2" style={{ color: 'var(--app-text-muted)' }}>Move this notebook to a different workspace</p>
                <div className="relative">
                  <select
                    value={editWorkspaceId || ''}
                    onChange={(e) => setEditWorkspaceId(e.target.value || null)}
                    className="w-full px-4 py-3 rounded-xl focus:outline-none cursor-pointer pr-10"
                    style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)', WebkitAppearance: 'none', MozAppearance: 'none', appearance: 'none' }}
                  >
                    <option value="" style={{ backgroundColor: 'var(--app-bg-secondary)', color: 'var(--app-text-primary)' }}>Uncategorized</option>
                    {workspaceList.map(ws => (
                      <option key={ws.id} value={ws.id} style={{ backgroundColor: 'var(--app-bg-secondary)', color: 'var(--app-text-primary)' }}>{ws.name}</option>
                    ))}
                  </select>
                  <div className="absolute inset-y-0 right-0 flex items-center pr-3 pointer-events-none">
                    <svg className="w-5 h-5" style={{ color: 'var(--app-text-muted)' }} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                    </svg>
                  </div>
                </div>
              </div>
              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => setEditingProject(null)} className="flex-1 px-4 py-2.5 rounded-xl" style={{ border: '1px solid var(--app-border-default)', color: 'var(--app-text-secondary)' }}>Cancel</button>
                <button type="submit" disabled={updating} className="flex-1 px-4 py-2.5 rounded-xl text-white font-medium disabled:opacity-50 flex items-center justify-center gap-2" style={{ background: 'var(--app-gradient-primary)' }}>
                  {updating && <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />}
                  Save
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Project Confirm */}
      {deleteConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => !deleting && setDeleteConfirm(null)} />
          <div className="relative w-full max-w-sm rounded-2xl shadow-2xl p-6" style={{ backgroundColor: 'var(--app-bg-secondary)', border: '1px solid rgba(239, 68, 68, 0.3)' }}>
            <h3 className="text-xl font-bold mb-2" style={{ color: 'var(--app-text-primary)' }}>Delete Notebook</h3>
            <p className="mb-4" style={{ color: 'var(--app-text-muted)' }}>Delete &quot;{deleteConfirm.name}&quot;? This cannot be undone.</p>
            <div className="flex gap-3">
              <button onClick={() => setDeleteConfirm(null)} disabled={deleting} className="flex-1 px-4 py-2.5 rounded-xl disabled:opacity-50" style={{ border: '1px solid var(--app-border-default)', color: 'var(--app-text-secondary)' }}>Cancel</button>
              <button onClick={confirmDeleteProject} disabled={deleting} className="flex-1 px-4 py-2.5 rounded-xl text-white font-medium disabled:opacity-50 flex items-center justify-center gap-2" style={{ backgroundColor: 'var(--app-accent-error)' }}>
                {deleting && <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />}
                Delete
              </button>
            </div>
          </div>
        </div>
      )}

      {/* New Workspace Modal */}
      {showNewWorkspace && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setShowNewWorkspace(false)} />
          <div className="relative w-full max-w-md rounded-2xl shadow-2xl p-6" style={{ backgroundColor: 'var(--app-bg-secondary)', border: '1px solid var(--app-border-default)' }}>
            <h3 className="text-xl font-bold mb-4" style={{ color: 'var(--app-text-primary)' }}>New Workspace</h3>
            <form onSubmit={handleCreateWorkspace} className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-2" style={{ color: 'var(--app-text-secondary)' }}>Name</label>
                <input type="text" value={newWorkspaceName} onChange={(e) => setNewWorkspaceName(e.target.value)} className="w-full px-4 py-3 rounded-xl focus:outline-none" style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }} placeholder="e.g., Machine Learning" required />
              </div>
              <div>
                <label className="block text-sm font-medium mb-2" style={{ color: 'var(--app-text-secondary)' }}>Color</label>
                <div className="flex flex-wrap gap-2">
                  {workspaceColors.map((color) => (
                    <button key={color.value} type="button" onClick={() => setNewWorkspaceColor(color.value)} className={`w-8 h-8 rounded-lg transition-all ${newWorkspaceColor === color.value ? 'ring-2 ring-white ring-offset-2 ring-offset-[#21222c] scale-110' : 'hover:scale-105'}`} style={{ backgroundColor: color.value }} title={color.name} />
                  ))}
                </div>
              </div>
              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => { setShowNewWorkspace(false); setNewWorkspaceName(''); setNewWorkspaceColor('#3B82F6') }} className="flex-1 px-4 py-2.5 rounded-xl" style={{ border: '1px solid var(--app-border-default)', color: 'var(--app-text-secondary)' }}>Cancel</button>
                <button type="submit" disabled={creatingWorkspace} className="flex-1 px-4 py-2.5 rounded-xl text-white font-medium disabled:opacity-50 flex items-center justify-center gap-2" style={{ background: 'var(--app-gradient-primary)' }}>
                  {creatingWorkspace && <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />}
                  Create
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Edit Workspace Modal */}
      {editingWorkspace && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setEditingWorkspace(null)} />
          <div className="relative w-full max-w-md rounded-2xl shadow-2xl p-6" style={{ backgroundColor: 'var(--app-bg-secondary)', border: '1px solid var(--app-border-default)' }}>
            <h3 className="text-xl font-bold mb-4" style={{ color: 'var(--app-text-primary)' }}>Edit Workspace</h3>
            <form onSubmit={handleUpdateWorkspace} className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-2" style={{ color: 'var(--app-text-secondary)' }}>Name</label>
                <input type="text" value={editWorkspaceName} onChange={(e) => setEditWorkspaceName(e.target.value)} className="w-full px-4 py-3 rounded-xl focus:outline-none" style={{ backgroundColor: 'var(--app-bg-input)', border: '1px solid var(--app-border-default)', color: 'var(--app-text-primary)' }} placeholder="Workspace name" required />
              </div>
              <div>
                <label className="block text-sm font-medium mb-2" style={{ color: 'var(--app-text-secondary)' }}>Color</label>
                <div className="flex flex-wrap gap-2">
                  {workspaceColors.map((color) => (
                    <button key={color.value} type="button" onClick={() => setEditWorkspaceColor(color.value)} className={`w-8 h-8 rounded-lg transition-all ${editWorkspaceColor === color.value ? 'ring-2 ring-white ring-offset-2 scale-110' : 'hover:scale-105'}`} style={{ backgroundColor: color.value }} title={color.name} />
                  ))}
                </div>
              </div>
              <div className="flex gap-3 pt-2">
                <button type="button" onClick={() => setEditingWorkspace(null)} className="flex-1 px-4 py-2.5 rounded-xl" style={{ border: '1px solid var(--app-border-default)', color: 'var(--app-text-secondary)' }}>Cancel</button>
                {!editingWorkspace.is_default && (
                  <button type="button" onClick={() => setDeleteWorkspaceConfirm(editingWorkspace)} className="px-4 py-2.5 rounded-xl" style={{ backgroundColor: 'rgba(239, 68, 68, 0.2)', color: 'var(--app-accent-error)', border: '1px solid rgba(239, 68, 68, 0.3)' }}>Delete</button>
                )}
                <button type="submit" disabled={updatingWorkspace} className="flex-1 px-4 py-2.5 rounded-xl text-white font-medium disabled:opacity-50 flex items-center justify-center gap-2" style={{ background: 'var(--app-gradient-primary)' }}>
                  {updatingWorkspace && <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />}
                  Save
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Workspace Confirm */}
      {deleteWorkspaceConfirm && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/60 backdrop-blur-sm" onClick={() => setDeleteWorkspaceConfirm(null)} />
          <div className="relative w-full max-w-sm rounded-2xl shadow-2xl p-6" style={{ backgroundColor: 'var(--app-bg-secondary)', border: '1px solid rgba(239, 68, 68, 0.3)' }}>
            <h3 className="text-xl font-bold mb-2" style={{ color: 'var(--app-text-primary)' }}>Delete Workspace</h3>
            <p className="mb-4" style={{ color: 'var(--app-text-muted)' }}>Delete &quot;{deleteWorkspaceConfirm.name}&quot; and all its notebooks? This cannot be undone.</p>
            <div className="flex gap-3">
              <button onClick={() => setDeleteWorkspaceConfirm(null)} className="flex-1 px-4 py-2.5 rounded-xl" style={{ border: '1px solid var(--app-border-default)', color: 'var(--app-text-secondary)' }}>Cancel</button>
              <button onClick={handleDeleteWorkspace} className="flex-1 px-4 py-2.5 rounded-xl text-white font-medium" style={{ backgroundColor: 'var(--app-accent-error)' }}>Delete</button>
            </div>
          </div>
        </div>
      )}

    </div>
  )
}
