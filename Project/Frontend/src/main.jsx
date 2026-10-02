import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import './admin-refresh.css'
import './auth-refresh.css'
import './responsive.css'
import App from './App.jsx'

createRoot(document.getElementById('root')).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
