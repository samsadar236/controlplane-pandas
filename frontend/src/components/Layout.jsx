import React from 'react'
import { Outlet } from 'react-router-dom'
import Navbar from './Navbar.jsx'

export default function Layout() {
  return (
    <div className="min-h-screen flex flex-col items-center p-8 text-gray-800">
      <Navbar />
      <main className="w-full max-w-5xl flex-grow flex flex-col pt-2 pb-8">
        <Outlet />
      </main>
      <footer className="w-full max-w-6xl mx-auto mt-20 pt-6 border-t border-gray-200 flex justify-between items-center text-sm text-gray-500">
        <span>GradeOps</span>
      </footer>
    </div>
  )
}
