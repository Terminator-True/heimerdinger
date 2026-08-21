import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Navbar } from './components/Navbar'
import { SettingsProvider } from './components/settings/SettingsProvider'
import { Placeholder } from './components/Placeholder'
import { LandingView } from './views/LandingView'
import { PlayerDashboardView } from './views/PlayerDashboardView'
import { GoldReportView } from './views/GoldReportView'
import { MatchDetailView } from './views/MatchDetailView'

export default function App() {
  return (
    <SettingsProvider>
      <BrowserRouter>
        <div className="min-h-screen bg-slate-950 text-slate-100">
          <Navbar />
          <Routes>
            <Route path="/" element={<LandingView />} />
            <Route path="/player/:puuid" element={<PlayerDashboardView />} />
            <Route
              path="/player/:puuid/gold"
              element={<GoldReportView />}
            />
            <Route
              path="/matches/:matchId"
              element={<Placeholder title="Detalle de partida" />}
            />
            <Route path="/coach" element={<Placeholder title="Coach IA" />} />
            <Route path="/team" element={<Placeholder title="Equipo" />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </BrowserRouter>
    </SettingsProvider>
  )
}
