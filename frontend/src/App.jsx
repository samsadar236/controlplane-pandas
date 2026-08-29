import React, { createContext, useEffect, useState } from 'react'
import { Routes, Route } from 'react-router-dom'
import { api } from './api'

import Layout from './components/Layout.jsx'
import Landing from './pages/Landing.jsx'
import Rubrics from './pages/Rubrics.jsx'
import Grading from './pages/Grading.jsx'
import Review from './pages/Review.jsx'
import Audit from './pages/Audit.jsx'

export const RoleContext = createContext({ role: 'instructor', user: null, users: [], setUser: () => {} })

export default function App() {
  const [users, setUsers] = useState([])
  const [user, setUser] = useState(null)
  const [health, setHealth] = useState(null)

  useEffect(() => {
    api.users().then(us => { setUsers(us); setUser(us[0] || null) }).catch(() => {})
    api.health().then(setHealth).catch(() => setHealth({ status: 'error' }))
  }, [])

  return (
    <RoleContext.Provider value={{ role: user?.role || 'instructor', user, users, setUser, health }}>
      <Routes>
        <Route path="/" element={<Landing />} />
        <Route element={<Layout />}>
          <Route path="/rubrics" element={<Rubrics />} />
          <Route path="/grading" element={<Grading />} />
          <Route path="/review" element={<Review />} />
          <Route path="/audit" element={<Audit />} />
        </Route>
      </Routes>
    </RoleContext.Provider>
  )
}
