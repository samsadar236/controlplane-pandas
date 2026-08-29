import React, { useContext } from 'react'
import { NavLink, useNavigate } from 'react-router-dom'
import { ClipboardCheck, GraduationCap, ScanEye, ShieldCheck, LogOut } from 'lucide-react'
import { RoleContext } from '../App.jsx'

const navItems = [
  { to: '/rubrics', label: 'Rubrics', icon: ClipboardCheck },
  { to: '/grading', label: 'Grading', icon: GraduationCap },
  { to: '/review',  label: 'Review',  icon: ScanEye },
  { to: '/audit',   label: 'Audit',   icon: ShieldCheck },
]

export default function Navbar() {
  const navigate = useNavigate()
  const { user, users, setUser, health } = useContext(RoleContext)

  return (
    <header className="w-full max-w-6xl mx-auto rounded-xl flex items-center justify-between px-6 py-3 nav-shadow mb-6 border border-gray-200 bg-white bg-opacity-80 backdrop-blur-sm">
      <div className="flex items-center space-x-8">
        {/* Logo */}
        <button onClick={() => navigate('/')} className="flex items-center space-x-2 group">
          <div className="w-7 h-7 bg-[#6b52c6] rounded flex items-center justify-center text-white font-bold text-sm">
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg"><path d="M5 13l4 4L19 7" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2"></path></svg>
          </div>
          <span className="font-bold text-lg text-gray-800 tracking-tight">GradeOps</span>
        </button>

        {/* Navigation Links */}
        <nav className="hidden md:flex space-x-1 text-sm font-medium text-gray-500">
          {navItems.map(({ to, label }) => (
            <NavLink
              key={to}
              to={to}
              className={({ isActive }) =>
                `px-4 py-2 rounded-md transition-all ${
                  isActive
                    ? 'text-[#6b52c6] bg-[#f3f0ff] font-semibold'
                    : 'text-gray-500 hover:text-gray-900 hover:bg-gray-100'
                }`
              }
            >
              {label}
            </NavLink>
          ))}
        </nav>
      </div>

      <div className="flex items-center gap-3">
        {/* Status Indicator */}
        {health && (
          <div className="flex items-center space-x-2 bg-gray-50 border border-gray-200 rounded-full px-3 py-1.5 text-sm text-gray-600">
            <span className={`w-2 h-2 rounded-full ${health.status === 'ok' ? 'bg-green-500' : 'bg-red-500'}`}></span>
            <span>{health.status === 'ok' ? 'Connected' : 'Disconnected'}</span>
          </div>
        )}

        {/* User selector */}
        {users.length > 0 && (
          <select
            value={user?.id || ''}
            onChange={(e) => setUser(users.find(u => String(u.id) === e.target.value))}
            className="h-9 px-2.5 pr-7 rounded-lg text-sm outline-none cursor-pointer bg-white border border-gray-300 text-gray-700 focus:border-[#6b52c6] focus:ring-2 focus:ring-[#6b52c6]/15"
          >
            {users.map(u => (
              <option key={u.id} value={u.id}>
                {u.role === 'instructor' ? 'Instructor' : 'TA'} · {u.name}
              </option>
            ))}
          </select>
        )}

        <button
          onClick={() => navigate('/')}
          className="h-9 w-9 rounded-lg flex items-center justify-center border border-gray-300 bg-white text-gray-500 hover:text-[#6b52c6] hover:border-[#6b52c6] transition"
          title="Back to landing"
        >
          <LogOut className="w-4 h-4" />
        </button>
      </div>
    </header>
  )
}
