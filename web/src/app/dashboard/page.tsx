'use client'

import { useEffect, useState, useCallback, useRef } from 'react'
import { useRouter } from 'next/navigation'
import Image from 'next/image'
import { auth, projects, playgrounds, notebooks, workspaces } from '@/lib/api'
import { getRelativeTime, sortByDateDesc } from '@/lib/dateUtils'
import { useAuthStore, useProjectsStore } from '@/lib/store'
import type { Project, Workspace } from '@/types'
import {
  Plus,
  Upload,
  Download,
  Play,
  Square,
  Trash2,
  Edit3,
  FileCode,
  Folder,
  FolderPlus,
  LogOut,
  Activity,
  MoreVertical,
  Check,
  X,
  ChevronRight,
  ChevronDown,
  Settings,
  RefreshCw,
  ExternalLink,
  BookOpen,
  Sparkles,
  CheckCircle,
  CloudUpload,
  User,
  FileText,
  Terminal,
} from 'lucide-react'

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
  const [playgroundLoadingOverlay, setPlaygroundLoadingOverlay] = useState(false)

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
  const [showProfileMenu, setShowProfileMenu] = useState(false)
  const profileMenuRef = useRef<HTMLDivElement>(null)

  // Modal states for Logs and Terminal
  const [logsModal, setLogsModal] = useState<{ projectId: string; projectName: string } | null>(null)
  const [terminalModal, setTerminalModal] = useState<{ projectId: string; projectName: string } | null>(null)

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

  const fetchPlaygroundStatus = useCallback(async (projectId?: string) => {
    try {
      // User-scoped: get the user's single playground
      const pg = await playgrounds.getStatus()
      if (pg && pg.project_id) {
        setPlaygroundStatuses(prev => {
          const newStatuses: typeof prev = {}
          // Mark all projects as stopped first
          for (const key of Object.keys(prev)) {
            newStatuses[key] = { status: 'stopped', loading: false }
          }
          // Mark the active project with actual status
          newStatuses[pg.project_id!] = {
            status: pg.status || 'stopped',
            loading: false,
            memory_limit_mb: pg.memory_limit_mb,
            cpu_limit: pg.cpu_limit,
          }
          return newStatuses
        })
      } else {
        // No running playground - mark all as stopped
        setPlaygroundStatuses(prev => {
          const newStatuses: typeof prev = {}
          for (const key of Object.keys(prev)) {
            newStatuses[key] = { status: 'stopped', loading: false }
          }
          return newStatuses
        })
      }
    } catch {
      if (projectId) {
        setPlaygroundStatuses(prev => ({
          ...prev,
          [projectId]: { status: 'stopped', loading: false }
        }))
      }
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
        localStorage.removeItem('access_token')
        localStorage.removeItem('refresh_token')
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
      // Only poll if any project is running or starting
      const hasActivePlayground = Object.values(playgroundStatuses).some(
        s => s.status === 'running' || s.status === 'starting'
      )
      if (!hasActivePlayground) return

      try {
        const pg = await playgrounds.getStatus()
        if (pg && pg.project_id) {
          setPlaygroundStatuses(prev => {
            const newStatuses: typeof prev = {}
            for (const key of Object.keys(prev)) {
              if (key === pg.project_id) {
                newStatuses[key] = {
                  status: pg.status || 'stopped',
                  loading: false,
                  memory_limit_mb: pg.memory_limit_mb,
                  cpu_limit: pg.cpu_limit,
                }
              } else if (prev[key]?.status !== 'stopped') {
                newStatuses[key] = { status: 'stopped', loading: false }
              } else {
                newStatuses[key] = prev[key]
              }
            }
            return newStatuses
          })
        } else {
          // No active playground - mark all as stopped
          setPlaygroundStatuses(prev => {
            const newStatuses: typeof prev = {}
            for (const key of Object.keys(prev)) {
              if (prev[key]?.status !== 'stopped') {
                newStatuses[key] = { status: 'stopped', loading: false }
              } else {
                newStatuses[key] = prev[key]
              }
            }
            return newStatuses
          })
        }
      } catch {
        // Ignore polling errors
      }
    }

    const interval = setInterval(pollStatuses, 10000) // Poll every 10 seconds
    return () => clearInterval(interval)
  }, [projectList, playgroundStatuses])

  const handleStartPlayground = async (projectId: string) => {
    setPlaygroundLoadingOverlay(true)
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
    } finally {
      setPlaygroundLoadingOverlay(false)
    }
  }

  const handleStopPlayground = async (projectId: string) => {
    setPlaygroundStatuses(prev => ({
      ...prev,
      [projectId]: { status: 'stopping', loading: true }
    }))
    try {
      await playgrounds.stop()
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
    setPlaygroundLoadingOverlay(true)
    setPlaygroundStatuses(prev => ({
      ...prev,
      [projectId]: { status: 'starting', loading: true }
    }))
    try {
      await playgrounds.stop()
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
    } finally {
      setPlaygroundLoadingOverlay(false)
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
        await playgrounds.stop()
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
    // Open logs in modal
    setLogsModal({ projectId: project.id, projectName: project.name })
  }

  const handleOpenTerminal = (project: Project) => {
    // Open terminal in modal
    setTerminalModal({ projectId: project.id, projectName: project.name })
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
    // Per-user model: stop the single user playground if running
    const hasRunning = Object.values(playgroundStatuses).some(s => s.status === 'running')
    if (hasRunning) {
      try {
        await playgrounds.stop()
      } catch {
        // Ignore errors
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

  // Get user initials for avatar
  const getUserInitials = () => {
    if (!user?.email) return '?'
    const parts = user.email.split('@')[0].split(/[._-]/)
    if (parts.length >= 2) {
      return (parts[0][0] + parts[1][0]).toUpperCase()
    }
    return user.email.substring(0, 2).toUpperCase()
  }

  // Close profile menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (profileMenuRef.current && !profileMenuRef.current.contains(event.target as Node)) {
        setShowProfileMenu(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

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
        <div className="fixed top-4 left-1/2 -translate-x-1/2 z-[100] max-w-lg w-full mx-4 animate-in slide-in-from-top duration-300">
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
              <Check className="w-5 h-5" style={{ color: 'var(--app-accent-success)' }} />
            </div>
            <div className="flex-1">
              <p className="text-sm" style={{ color: 'var(--app-accent-success)' }}>{notificationMessage}</p>
            </div>
            <button
              onClick={() => setNotificationMessage(null)}
              className="flex-shrink-0 transition-colors hover:opacity-80"
              style={{ color: 'var(--app-accent-success)' }}
            >
              <X className="w-5 h-5" />
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

      {/* Header - Full width */}
      <header
        className="relative z-50 backdrop-blur-xl"
        style={{
          backgroundColor: 'var(--app-bg-secondary)',
          borderBottom: '1px solid var(--app-border-default)'
        }}
      >
        <div className="px-6 py-3">
          <div className="flex justify-between items-center">
            <div className="flex items-center gap-3">
              <Image
                src="/a7ac5906-c5c1-4819-b60b-6141da54bf2f.png"
                alt="AI Notebook"
                width={40}
                height={40}
                className="rounded-xl"
                style={{ objectFit: 'contain' }}
              />
              <div>
                <h1 className="text-base font-bold" style={{ color: 'var(--app-text-primary)' }}>AI Notebook</h1>
                <p className="text-xs" style={{ color: 'var(--app-accent-primary)' }}>Intelligent Computing Environment</p>
              </div>
            </div>
            {/* Profile Menu */}
            <div className="relative z-50" ref={profileMenuRef}>
              <button
                onClick={() => setShowProfileMenu(!showProfileMenu)}
                className="flex items-center gap-2.5 px-3 py-1.5 rounded-full transition-all hover:bg-white/5"
              >
                <div
                  className="w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold ring-2 ring-transparent hover:ring-white/20 transition-all"
                  style={{
                    background: 'var(--app-gradient-primary)',
                    color: 'white'
                  }}
                >
                  {getUserInitials()}
                </div>
                <span className="text-sm font-medium" style={{ color: 'var(--app-text-primary)' }}>
                  {user?.email?.split('@')[0]}
                </span>
                <ChevronDown
                  className={`w-3.5 h-3.5 transition-transform duration-200 ${showProfileMenu ? 'rotate-180' : ''}`}
                  style={{ color: 'var(--app-text-muted)' }}
                />
              </button>

              {/* Dropdown Menu */}
              {showProfileMenu && (
                <div
                  className="absolute right-0 top-full mt-2 w-64 rounded-xl shadow-2xl overflow-hidden z-50 animate-in fade-in slide-in-from-top-2 duration-200"
                  style={{
                    backgroundColor: 'var(--app-bg-secondary)',
                    border: '1px solid var(--app-border-default)'
                  }}
                >
                  {/* User Info */}
                  <div className="p-4" style={{ borderBottom: '1px solid var(--app-border-default)' }}>
                    <div className="flex items-center gap-3">
                      <div
                        className="w-10 h-10 rounded-full flex items-center justify-center text-sm font-semibold"
                        style={{
                          background: 'var(--app-gradient-primary)',
                          color: 'white'
                        }}
                      >
                        {getUserInitials()}
                      </div>
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate" style={{ color: 'var(--app-text-primary)' }}>
                          {user?.email?.split('@')[0]}
                        </p>
                        <p className="text-xs truncate" style={{ color: 'var(--app-text-muted)' }}>
                          {user?.email}
                        </p>
                      </div>
                    </div>
                  </div>

                  {/* Settings Link */}
                  <div className="p-2" style={{ borderBottom: '1px solid var(--app-border-default)' }}>
                    <button
                      onClick={() => { setShowProfileMenu(false); router.push('/settings') }}
                      className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all text-left"
                      style={{ color: 'var(--app-text-secondary)' }}
                      onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--app-bg-tertiary)'}
                      onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                    >
                      <Settings className="w-4 h-4" />
                      <span className="text-sm">Settings & API Keys</span>
                    </button>
                  </div>

                  {/* Admin Link */}
                  {user?.is_admin && (
                    <div className="p-2" style={{ borderBottom: '1px solid var(--app-border-default)' }}>
                      <button
                        onClick={() => { setShowProfileMenu(false); router.push('/admin') }}
                        className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all text-left"
                        style={{ color: 'var(--app-text-secondary)' }}
                        onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'var(--app-bg-tertiary)'}
                        onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                      >
                        <Settings className="w-4 h-4" />
                        <span className="text-sm">Admin Dashboard</span>
                      </button>
                    </div>
                  )}

                  {/* Sign Out */}
                  <div className="p-2">
                    <button
                      onClick={() => { setShowProfileMenu(false); handleLogout() }}
                      className="w-full flex items-center gap-3 px-3 py-2.5 rounded-lg transition-all text-left"
                      style={{ color: 'var(--app-accent-error)' }}
                      onMouseEnter={(e) => e.currentTarget.style.backgroundColor = 'rgba(239, 68, 68, 0.1)'}
                      onMouseLeave={(e) => e.currentTarget.style.backgroundColor = 'transparent'}
                    >
                      <LogOut className="w-4 h-4" />
                      <span className="text-sm">Sign Out</span>
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Main Content - 3 Column Layout */}
      <div className="relative z-10 flex h-[calc(100vh-57px)]">
        {/* Left Sidebar - Workspaces */}
        <aside
          className="w-[15%] min-w-[200px] max-w-[280px] flex-shrink-0 overflow-y-auto"
          style={{
            backgroundColor: 'var(--app-bg-secondary)',
            borderRight: '1px solid var(--app-border-default)'
          }}
        >
          <div className="p-4">
            {/* New Notebook Button */}
            <button
              onClick={() => setShowNewProject(true)}
              className="w-full px-4 py-2.5 text-white rounded-lg font-medium text-sm shadow-lg transition-all duration-300 flex items-center justify-center gap-2 hover:opacity-90 mb-4"
              style={{
                background: 'var(--app-gradient-primary)',
                boxShadow: '0 4px 20px rgba(59, 130, 246, 0.3)'
              }}
            >
              <Plus className="w-4 h-4" />
              New Notebook
            </button>

            {/* Import Button */}
            <button
              onClick={() => setShowImportModal(true)}
              className="w-full px-4 py-2 rounded-lg font-medium text-sm transition-all duration-300 flex items-center justify-center gap-2 hover:opacity-90 mb-6"
              style={{
                backgroundColor: 'var(--app-bg-card)',
                color: 'var(--app-text-secondary)',
                border: '1px solid var(--app-border-default)'
              }}
            >
              <Upload className="w-4 h-4" />
              Import .ipynb
            </button>

            {/* Workspaces Section */}
            <div className="mb-2 flex items-center justify-between">
              <h3 className="text-xs font-semibold uppercase tracking-wider" style={{ color: 'var(--app-text-muted)' }}>Workspaces</h3>
              <button
                onClick={() => setShowNewWorkspace(true)}
                className="p-1 rounded transition-all hover:opacity-80"
                style={{ color: 'var(--app-text-muted)' }}
                title="New Workspace"
              >
                <Plus className="w-3.5 h-3.5" />
              </button>
            </div>

            {/* Workspace Items */}
            <div className="space-y-0.5">
              {workspaceList.map(ws => (
                <div
                  key={ws.id}
                  className="group flex items-center gap-2 px-2 py-1.5 rounded-lg transition-all cursor-pointer"
                  style={{
                    backgroundColor: selectedWorkspaceId === ws.id ? 'var(--app-bg-input)' : 'transparent',
                    color: selectedWorkspaceId === ws.id ? 'var(--app-text-primary)' : 'var(--app-text-muted)'
                  }}
                  onClick={() => setSelectedWorkspaceId(ws.id)}
                >
                  <div
                    className="w-2.5 h-2.5 rounded-full flex-shrink-0"
                    style={{ backgroundColor: ws.color }}
                  />
                  <span className="flex-1 text-sm truncate">{ws.name}</span>
                  <button
                    onClick={(e) => { e.stopPropagation(); handleEditWorkspace(ws) }}
                    className="p-0.5 opacity-0 group-hover:opacity-100 transition-all"
                    style={{ color: 'var(--app-text-muted)' }}
                    title="Edit workspace"
                  >
                    <Edit3 className="w-3 h-3" />
                  </button>
                  <span className="text-xs" style={{ color: 'var(--app-text-muted)' }}>{ws.project_count}</span>
                </div>
              ))}

              {/* Uncategorized */}
              {uncategorizedCount > 0 && (
                <button
                  onClick={() => setSelectedWorkspaceId('uncategorized')}
                  className="w-full flex items-center gap-2 px-2 py-1.5 rounded-lg transition-all"
                  style={{
                    backgroundColor: selectedWorkspaceId === 'uncategorized' ? 'var(--app-bg-input)' : 'transparent',
                    color: selectedWorkspaceId === 'uncategorized' ? 'var(--app-text-primary)' : 'var(--app-text-muted)'
                  }}
                >
                  <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ backgroundColor: 'var(--app-text-muted)' }} />
                  <span className="flex-1 text-left text-sm">Uncategorized</span>
                  <span className="text-xs" style={{ color: 'var(--app-text-muted)' }}>{uncategorizedCount}</span>
                </button>
              )}
            </div>
          </div>
        </aside>

        {/* Center - Main Content */}
        <main className="flex-1 overflow-y-auto p-6">
          {/* Workspace Header */}
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-3">
              {getSelectedWorkspace() && (
                <div
                  className="w-3 h-3 rounded-full"
                  style={{ backgroundColor: getSelectedWorkspace()?.color }}
                />
              )}
              <h2 className="text-lg font-semibold" style={{ color: 'var(--app-text-primary)' }}>{getSelectedWorkspaceName()}</h2>
              <span className="text-sm" style={{ color: 'var(--app-text-muted)' }}>
                {getFilteredProjects().length} notebook{getFilteredProjects().length !== 1 ? 's' : ''}
              </span>
            </div>
          </div>

          {/* Projects Content */}
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
                  <BookOpen className="w-8 h-8" style={{ color: 'var(--app-text-muted)' }} strokeWidth={1.5} />
                </div>
                <h4 className="text-base font-medium mb-2" style={{ color: 'var(--app-text-primary)' }}>No notebooks here</h4>
                <p className="mb-4 text-xs" style={{ color: 'var(--app-text-muted)' }}>Create a notebook in this workspace</p>
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
                          <BookOpen className="w-4 h-4" />
                        </div>
                        <div className="min-w-0">
                          <h4
                            className={`font-medium truncate text-sm ${isRunning ? 'cursor-pointer hover:underline' : ''}`}
                            style={{ color: 'var(--app-text-primary)' }}
                            onClick={() => isRunning && router.push(`/notebook/${project.id}`)}
                          >{project.name}</h4>
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
                        {getRelativeTime(project.updated_at)}
                      </div>

                      {/* Actions */}
                      <div className="col-span-4 flex items-center justify-end gap-1.5">
                        {/* Playground Controls */}
                        {!isRunning ? (
                          <button
                            onClick={() => handleStartPlayground(project.id)}
                            disabled={isLoading}
                            className="px-3 py-1.5 text-xs rounded-lg transition-all disabled:opacity-50 flex items-center gap-1.5"
                            style={{
                              backgroundColor: 'rgba(59, 130, 246, 0.2)',
                              color: 'var(--app-accent-primary)',
                              border: '1px solid rgba(59, 130, 246, 0.3)'
                            }}
                          >
                            {isLoading ? (
                              <div className="w-3 h-3 border-2 rounded-full animate-spin" style={{ borderColor: 'rgba(59, 130, 246, 0.3)', borderTopColor: 'var(--app-accent-primary)' }} />
                            ) : (
                              <Play className="w-3 h-3" />
                            )}
                            Start
                          </button>
                        ) : (
                          <>
                            {/* Stop - icon only */}
                            <button
                              onClick={() => handleStopPlayground(project.id)}
                              disabled={isLoading}
                              className="p-1.5 rounded-lg transition-all disabled:opacity-50"
                              style={{
                                backgroundColor: 'rgba(239, 68, 68, 0.2)',
                                color: 'var(--app-accent-error)',
                                border: '1px solid rgba(239, 68, 68, 0.3)'
                              }}
                              title="Stop playground"
                            >
                              <Square className="w-4 h-4" fill="currentColor" />
                            </button>
                            {/* Logs - icon only */}
                            <button
                              onClick={() => handleViewLogs(project)}
                              className="p-1.5 rounded-lg transition-all"
                              style={{
                                backgroundColor: 'rgba(59, 130, 246, 0.2)',
                                color: 'var(--app-accent-primary)',
                                border: '1px solid rgba(59, 130, 246, 0.3)'
                              }}
                              title="View logs"
                            >
                              <FileText className="w-4 h-4" />
                            </button>
                            {/* Terminal - icon only */}
                            <button
                              onClick={() => handleOpenTerminal(project)}
                              className="p-1.5 rounded-lg transition-all"
                              style={{
                                backgroundColor: 'rgba(20, 184, 166, 0.2)',
                                color: 'var(--app-accent-secondary)',
                                border: '1px solid rgba(20, 184, 166, 0.3)'
                              }}
                              title="Open Terminal"
                            >
                              <Terminal className="w-4 h-4" />
                            </button>
                            {/* Open */}
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

                        {/* More Actions - always visible on hover */}
                        <div className="flex items-center gap-0.5 opacity-0 group-hover:opacity-100 transition-all ml-1 pl-1.5" style={{ borderLeft: '1px solid var(--app-border-default)' }}>
                          <button
                            onClick={() => handleDownloadProject(project)}
                            disabled={downloadingProject === project.id}
                            className="p-1.5 rounded-lg transition-all disabled:opacity-50 hover:bg-white/5"
                            style={{ color: 'var(--app-text-muted)' }}
                            title="Download notebook"
                          >
                            {downloadingProject === project.id ? (
                              <div className="w-4 h-4 border-2 rounded-full animate-spin" style={{ borderColor: 'rgba(20, 184, 166, 0.3)', borderTopColor: 'var(--app-accent-secondary)' }} />
                            ) : (
                              <Download className="w-4 h-4" />
                            )}
                          </button>
                          <button
                            onClick={() => handleEditProject(project)}
                            className="p-1.5 rounded-lg transition-all hover:bg-white/5"
                            style={{ color: 'var(--app-text-muted)' }}
                            title="Edit notebook"
                          >
                            <Edit3 className="w-4 h-4" />
                          </button>
                          <button
                            onClick={() => handleDeleteProject(project)}
                            className="p-1.5 rounded-lg transition-all hover:bg-red-500/10"
                            style={{ color: 'var(--app-accent-error)' }}
                            title="Delete notebook"
                          >
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
        </main>

        {/* Right Sidebar - Stats & Activity */}
        <aside
          className="w-[18%] min-w-[220px] max-w-[300px] flex-shrink-0 overflow-y-auto p-4"
          style={{
            backgroundColor: 'var(--app-bg-secondary)',
            borderLeft: '1px solid var(--app-border-default)'
          }}
        >
          {/* Stats Cards */}
          <div className="space-y-3 mb-6">
            <div
              className="p-4 rounded-xl relative overflow-hidden"
              style={{
                backgroundColor: 'var(--app-bg-card)',
                border: '1px solid var(--app-border-default)'
              }}
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs" style={{ color: 'var(--app-text-muted)' }}>Total Notebooks</p>
                  <p className="text-xl font-bold mt-0.5" style={{ color: 'var(--app-text-primary)' }}>{projectList.length}</p>
                </div>
                <BookOpen className="w-8 h-8" style={{ color: 'var(--app-accent-primary)' }} strokeWidth={1.5} />
              </div>
            </div>
            <div
              className="p-4 rounded-xl relative overflow-hidden"
              style={{
                backgroundColor: 'var(--app-bg-card)',
                border: '1px solid var(--app-border-default)'
              }}
            >
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-xs" style={{ color: 'var(--app-text-muted)' }}>Active Playgrounds</p>
                  <p className="text-xl font-bold mt-0.5" style={{ color: 'var(--app-text-primary)' }}>{activePlaygrounds}</p>
                </div>
                <Sparkles className="w-8 h-8" style={{ color: 'var(--app-accent-success)' }} strokeWidth={1.5} />
              </div>
            </div>
          </div>

          {/* Recent Projects */}
          <div>
            <h3 className="text-xs font-semibold uppercase tracking-wider mb-3" style={{ color: 'var(--app-text-muted)' }}>Recent Projects</h3>
            <div className="space-y-1.5">
              {sortByDateDesc(projectList, 'updated_at').slice(0, 5).map(project => {
                const pgStatus = playgroundStatuses[project.id]
                const isRunning = pgStatus?.status === 'running'
                return (
                  <div
                    key={project.id}
                    onClick={() => isRunning && router.push(`/notebook/${project.id}`)}
                    className={`p-2.5 rounded-lg text-sm transition-all ${isRunning ? 'cursor-pointer hover:opacity-80' : ''}`}
                    style={{
                      backgroundColor: 'var(--app-bg-card)',
                      border: '1px solid var(--app-border-default)'
                    }}
                  >
                    <div className="flex items-center gap-2 mb-1">
                      {/* Status indicator */}
                      <div
                        className={`w-2 h-2 rounded-full flex-shrink-0 ${pgStatus?.status === 'starting' || pgStatus?.status === 'stopping' ? 'animate-pulse' : ''}`}
                        style={{
                          backgroundColor: isRunning ? 'var(--app-accent-success)' :
                            pgStatus?.status === 'starting' || pgStatus?.status === 'stopping' ? 'var(--app-accent-warning)' :
                            'var(--app-text-muted)',
                          boxShadow: isRunning ? '0 0 6px rgba(16, 185, 129, 0.5)' : 'none'
                        }}
                      />
                      <p className="truncate flex-1" style={{ color: 'var(--app-text-primary)' }}>{project.name}</p>
                    </div>
                    <p className="text-xs pl-4" style={{ color: 'var(--app-text-muted)' }}>
                      {getRelativeTime(project.updated_at)}
                    </p>
                  </div>
                )
              })}
              {projectList.length === 0 && (
                <p className="text-sm" style={{ color: 'var(--app-text-muted)' }}>No projects yet</p>
              )}
            </div>
          </div>
        </aside>
      </div>

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
            <h3 className="text-base font-bold mb-4" style={{ color: 'var(--app-text-primary)' }}>New Notebook</h3>
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
            <h3 className="text-base font-bold mb-4" style={{ color: 'var(--app-text-primary)' }}>Import Notebook</h3>
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
                      <CheckCircle className="w-8 h-8 mx-auto mb-2" style={{ color: 'var(--app-accent-primary)' }} />
                      <p className="font-medium" style={{ color: 'var(--app-accent-primary)' }}>{importFile.name}</p>
                    </>
                  ) : (
                    <>
                      <CloudUpload className="w-8 h-8 mx-auto mb-2" style={{ color: 'var(--app-text-muted)' }} />
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
            <h3 className="text-base font-bold mb-4" style={{ color: 'var(--app-text-primary)' }}>Edit Notebook</h3>
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
                    <ChevronDown className="w-5 h-5" style={{ color: 'var(--app-text-muted)' }} />
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
            <h3 className="text-base font-bold mb-2" style={{ color: 'var(--app-text-primary)' }}>Delete Notebook</h3>
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
            <h3 className="text-base font-bold mb-4" style={{ color: 'var(--app-text-primary)' }}>New Workspace</h3>
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
            <h3 className="text-base font-bold mb-4" style={{ color: 'var(--app-text-primary)' }}>Edit Workspace</h3>
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
            <h3 className="text-base font-bold mb-2" style={{ color: 'var(--app-text-primary)' }}>Delete Workspace</h3>
            <p className="mb-4" style={{ color: 'var(--app-text-muted)' }}>Delete &quot;{deleteWorkspaceConfirm.name}&quot; and all its notebooks? This cannot be undone.</p>
            <div className="flex gap-3">
              <button onClick={() => setDeleteWorkspaceConfirm(null)} className="flex-1 px-4 py-2.5 rounded-xl" style={{ border: '1px solid var(--app-border-default)', color: 'var(--app-text-secondary)' }}>Cancel</button>
              <button onClick={handleDeleteWorkspace} className="flex-1 px-4 py-2.5 rounded-xl text-white font-medium" style={{ backgroundColor: 'var(--app-accent-error)' }}>Delete</button>
            </div>
          </div>
        </div>
      )}

      {/* Playground Loading Overlay */}
      {playgroundLoadingOverlay && (
        <div className="fixed inset-0 bg-black/60 backdrop-blur-sm flex items-center justify-center z-50">
          <div
            className="rounded-xl p-8 max-w-sm mx-4 shadow-2xl text-center"
            style={{
              backgroundColor: 'var(--app-bg-secondary)',
              border: '1px solid var(--app-border-default)',
            }}
          >
            <div className="relative w-16 h-16 mx-auto mb-4">
              {/* Outer spinning ring */}
              <div className="absolute inset-0 border-4 border-blue-500/20 rounded-full" />
              <div className="absolute inset-0 border-4 border-transparent border-t-blue-500 rounded-full animate-spin" />
              {/* Inner pulsing circle */}
              <div className="absolute inset-3 bg-gradient-to-br from-blue-500 to-teal-500 rounded-full animate-pulse" />
            </div>
            <h3 className="text-base font-semibold mb-2" style={{ color: 'var(--app-text-primary)' }}>
              Starting Playground
            </h3>
            <p className="text-sm" style={{ color: 'var(--app-text-muted)' }}>
              Setting up your Python environment...
            </p>
            <div className="mt-4 flex justify-center gap-1">
              <span className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '0ms' }} />
              <span className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '150ms' }} />
              <span className="w-2 h-2 bg-blue-500 rounded-full animate-bounce" style={{ animationDelay: '300ms' }} />
            </div>
          </div>
        </div>
      )}

      {/* Logs Modal */}
      {logsModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={() => setLogsModal(null)} />
          <div
            className="relative w-full max-w-6xl h-[90vh] rounded-2xl shadow-2xl overflow-hidden flex flex-col"
            style={{
              backgroundColor: 'var(--app-bg-secondary)',
              border: '1px solid var(--app-border-default)'
            }}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3" style={{ borderBottom: '1px solid var(--app-border-default)' }}>
              <div className="flex items-center gap-3">
                <FileText className="w-5 h-5" style={{ color: 'var(--app-accent-primary)' }} />
                <div>
                  <h3 className="text-sm font-semibold" style={{ color: 'var(--app-text-primary)' }}>Playground Logs</h3>
                  <p className="text-xs" style={{ color: 'var(--app-text-muted)' }}>{logsModal.projectName}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => window.open(`/logs/${logsModal.projectId}`, '_blank')}
                  className="p-2 rounded-lg transition-all hover:bg-white/5"
                  style={{ color: 'var(--app-text-muted)' }}
                  title="Open in new tab"
                >
                  <ExternalLink className="w-4 h-4" />
                </button>
                <button
                  onClick={() => setLogsModal(null)}
                  className="p-2 rounded-lg transition-all hover:bg-white/5"
                  style={{ color: 'var(--app-text-muted)' }}
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>
            {/* Iframe */}
            <div className="flex-1 min-h-0 overflow-hidden">
              <iframe
                src={`/logs/${logsModal.projectId}`}
                className="w-full h-full border-0"
                title="Playground Logs"
              />
            </div>
          </div>
        </div>
      )}

      {/* Terminal Modal */}
      {terminalModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={() => setTerminalModal(null)} />
          <div
            className="relative w-full max-w-6xl h-[90vh] rounded-2xl shadow-2xl overflow-hidden flex flex-col"
            style={{
              backgroundColor: 'var(--app-bg-secondary)',
              border: '1px solid var(--app-border-default)'
            }}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3" style={{ borderBottom: '1px solid var(--app-border-default)' }}>
              <div className="flex items-center gap-3">
                <Terminal className="w-5 h-5" style={{ color: 'var(--app-accent-secondary)' }} />
                <div>
                  <h3 className="text-sm font-semibold" style={{ color: 'var(--app-text-primary)' }}>Container Terminal</h3>
                  <p className="text-xs" style={{ color: 'var(--app-text-muted)' }}>{terminalModal.projectName}</p>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={() => window.open(`/terminal/${terminalModal.projectId}`, '_blank')}
                  className="p-2 rounded-lg transition-all hover:bg-white/5"
                  style={{ color: 'var(--app-text-muted)' }}
                  title="Open in new tab"
                >
                  <ExternalLink className="w-4 h-4" />
                </button>
                <button
                  onClick={() => setTerminalModal(null)}
                  className="p-2 rounded-lg transition-all hover:bg-white/5"
                  style={{ color: 'var(--app-text-muted)' }}
                >
                  <X className="w-4 h-4" />
                </button>
              </div>
            </div>
            {/* Iframe */}
            <div className="flex-1 min-h-0 overflow-hidden">
              <iframe
                src={`/terminal/${terminalModal.projectId}`}
                className="w-full h-full border-0"
                title="Container Terminal"
              />
            </div>
          </div>
        </div>
      )}

    </div>
  )
}
