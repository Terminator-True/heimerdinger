import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { Navbar } from './components/Navbar'
import { SettingsProvider } from './components/settings/SettingsProvider'
import { LandingView } from './views/LandingView'
import { PlayerDashboardView } from './views/PlayerDashboardView'
import { GoldReportView } from './views/GoldReportView'
import { MatchDetailView } from './views/MatchDetailView'
import { CoachView } from './views/CoachView'
import { TeamView } from './views/TeamView'

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
              element={<MatchDetailView />}
            />
            <Route path="/coach" element={<CoachView />} />
            <Route path="/team" element={<TeamView />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </div>
      </BrowserRouter>
    </SettingsProvider>
  )
}
