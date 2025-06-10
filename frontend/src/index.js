import React from 'react';
import ReactDOM from 'react-dom/client';
import './index.css';
import App from './App';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
EOF

# Make sure App.jsx imports LeaderboardPage correctly
cat > src/App.jsx << 'EOF'
import React from 'react';
import LeaderboardPage from './pages/LeaderboardPage';

function App() {
  return (
    <div className="App">
      <LeaderboardPage />
    </div>
  );
}

export default App;
