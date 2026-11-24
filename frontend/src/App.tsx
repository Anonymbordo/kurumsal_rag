import { BrowserRouter, Route, Routes } from 'react-router-dom'
import { Sidebar } from './components/Sidebar'
import { AppProvider } from './context'
import Chat from './pages/Chat'
import Home from './pages/Home'
import Labeling from './pages/Labeling'
import Dashboard from './pages/Dashboard'
import Documents from './pages/Documents'
import Meeting from './pages/Meeting'
import Meetings from './pages/Meetings'
import Review from './pages/Review'
import TaskSourceView from './pages/TaskSourceView'
import Team from './pages/Team'
import Upload from './pages/Upload'

export default function App() {
  return (
    <AppProvider>
      <BrowserRouter>
        <div className="shell">
          <Sidebar />
          <div className="content">
            <Routes>
              <Route path="/" element={<Home />} />
              <Route path="/c/:id" element={<Chat />} />
              <Route path="/yukle" element={<Upload />} />
              <Route path="/dokuman/:id" element={<Review />} />
              <Route path="/dokumanlar" element={<Documents />} />
              <Route path="/toplantilar" element={<Meetings />} />
              <Route path="/pano" element={<Dashboard />} />
              <Route path="/gorev/:id" element={<TaskSourceView />} />
              <Route path="/toplanti/:id" element={<Meeting />} />
              <Route path="/ekip" element={<Team />} />
              <Route path="/etiketle" element={<Labeling />} />
              <Route path="*" element={<div className="center-msg">Sayfa bulunamadı</div>} />
            </Routes>
          </div>
        </div>
      </BrowserRouter>
    </AppProvider>
  )
}
