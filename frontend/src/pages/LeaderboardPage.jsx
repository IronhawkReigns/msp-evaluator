import React, { useEffect, useState } from "react";
import axios from "axios";
import { Trophy, Medal, Award, TrendingUp, Users, Cpu, Settings, Eye, Filter, RefreshCw } from "lucide-react";
import { Zap, Star, Target } from "lucide-react";

// Environment-aware API URL
const API_BASE = 'https://mspevaluator.duckdns.org';

// Component for score visualization bars
const ScoreBar = ({ score, maxScore = 5, color = "blue" }) => {
  const percentage = (score / maxScore) * 100;
  const colorClasses = {
    blue: "bg-blue-500",
    green: "bg-green-500", 
    purple: "bg-purple-500",
    orange: "bg-orange-500"
  };

  return (
    <div className="w-full bg-gray-200 rounded-full h-2">
      <div
        className={`h-2 rounded-full ${colorClasses[color]} transition-all duration-300`}
        style={{ width: `${percentage}%` }}
      />
    </div>
  );
};

// Component for rank badges (trophy, medal, etc.)
const RankBadge = ({ rank }) => {
  if (rank === 1) return <Trophy className="w-6 h-6 text-yellow-500" />;
  if (rank === 2) return <Medal className="w-6 h-6 text-gray-400" />;
  if (rank === 3) return <Award className="w-6 h-6 text-amber-600" />;
  return <span className="w-6 h-6 flex items-center justify-center text-gray-600 font-bold">{rank}</span>;
};

// Component for category icons
const CategoryIcon = ({ category }) => {
  const icons = {
    "인적역량": <Users className="w-4 h-4" />,
    "AI기술역량": <Cpu className="w-4 h-4" />,
    "솔루션 역량": <Settings className="w-4 h-4" />
  };
  return icons[category] || <TrendingUp className="w-4 h-4" />;
};

// Individual MSP card component
const MSPCard = ({ msp, rank, onSelect }) => {
  const categories = Object.entries(msp.category_scores || {});
  
  return (
    <div className="bg-white rounded-lg shadow-md hover:shadow-lg transition-all duration-300 border border-gray-200 hover:border-blue-300">
      <div className="p-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <RankBadge rank={rank} />
            <div>
              <h3 className="text-lg font-bold text-gray-900">{msp.name}</h3>
              <p className="text-sm text-gray-500">MSP 파트너</p>
            </div>
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold text-blue-600">{msp.total_score.toFixed(1)}</div>
            <div className="text-xs text-gray-500">총점</div>
          </div>
        </div>

        {/* Score Visualization */}
        <div className="mb-4">
          <div className="flex justify-between items-center mb-2">
            <span className="text-sm font-medium text-gray-700">종합 점수</span>
            <span className="text-sm text-gray-600">{msp.total_score.toFixed(1)}/5</span>
          </div>
          <ScoreBar score={msp.total_score} maxScore={5} color="blue" />
        </div>

        {/* Category Scores */}
        <div className="space-y-3 mb-4">
          {categories.map(([category, score]) => (
            <div key={category} className="flex items-center gap-3">
              <CategoryIcon category={category} />
              <div className="flex-1">
                <div className="flex justify-between items-center mb-1">
                  <span className="text-sm font-medium text-gray-700">{category}</span>
                  <span className="text-sm text-gray-600">{score.toFixed(1)}</span>
                </div>
                <ScoreBar 
                  score={score} 
                  maxScore={5}
                  color={category === "인적역량" ? "green" : category === "AI기술역량" ? "purple" : "orange"} 
                />
              </div>
            </div>
          ))}
        </div>

        {/* Action Button */}
        <button
          onClick={() => onSelect(msp)}
          className="w-full bg-gray-50 hover:bg-blue-50 border border-gray-200 hover:border-blue-300 rounded-md py-2 px-4 text-sm font-medium text-gray-700 hover:text-blue-700 transition-colors duration-200 flex items-center justify-center gap-2"
        >
          <Eye className="w-4 h-4" />
          상세 정보 보기
        </button>
      </div>
    </div>
  );
};

// Enhanced modal component
const MSPModal = ({ msp, onClose }) => {
  if (!msp) return null;
  
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex justify-center items-center z-50 p-4">
      <div className="bg-white rounded-lg shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
        <div className="p-6">
          {/* Header */}
          <div className="flex justify-between items-start mb-6">
            <div>
              <h2 className="text-2xl font-bold text-gray-900">{msp.name}</h2>
              <p className="text-gray-600">MSP 파트너사 상세 정보</p>
            </div>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-gray-600 text-2xl font-light"
            >
              ×
            </button>
          </div>

          {/* Total Score */}
          <div className="bg-blue-50 rounded-lg p-4 mb-6">
            <div className="text-center">
              <div className="text-3xl font-bold text-blue-600 mb-1">{msp.total_score.toFixed(1)}</div>
              <div className="text-sm text-blue-700">총점 (5점 만점)</div>
              <div className="mt-2">
                <ScoreBar score={msp.total_score} maxScore={5} color="blue" />
              </div>
            </div>
          </div>

          {/* Category Breakdown */}
          <div className="space-y-4">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">역량별 상세 점수</h3>
            {Object.entries(msp.category_scores || {}).map(([category, score]) => (
              <div key={category} className="border rounded-lg p-4">
                <div className="flex items-center gap-3 mb-3">
                  <CategoryIcon category={category} />
                  <div className="flex-1">
                    <div className="flex justify-between items-center">
                      <h4 className="font-medium text-gray-900">{category}</h4>
                      <span className="text-lg font-semibold text-gray-700">{score.toFixed(1)}/5</span>
                    </div>
                  </div>
                </div>
                <ScoreBar 
                  score={score} 
                  maxScore={5}
                  color={category === "인적역량" ? "green" : category === "AI기술역량" ? "purple" : "orange"} 
                />
                <div className="mt-2 text-xs text-gray-500">
                  {score >= 4 ? "우수" : score >= 3 ? "양호" : score >= 2 ? "보통" : "개선 필요"}
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};

// Filter controls component with refresh functionality
const ModernFilterDropdown = ({ sortBy, setSortBy, refreshMessage }) => {
  return (
    <div className="mb-8">
      {/* Refresh Message */}
      {refreshMessage && (
        <div className={`mb-6 p-4 rounded-xl backdrop-blur-sm border ${
          refreshMessage.includes('✅') 
            ? 'bg-green-50 bg-opacity-80 text-green-800 border-green-200' 
            : 'bg-red-50 bg-opacity-80 text-red-800 border-red-200'
        }`}>
          <div className="flex items-center gap-2">
            {refreshMessage.includes('✅') ? (
              <div className="w-5 h-5 bg-green-500 rounded-full flex items-center justify-center">
                <div className="w-2 h-2 bg-white rounded-full"></div>
              </div>
            ) : (
              <div className="w-5 h-5 bg-red-500 rounded-full flex items-center justify-center">
                <div className="w-2 h-2 bg-white rounded-full"></div>
              </div>
            )}
            {refreshMessage}
          </div>
        </div>
      )}
      
      {/* Filter controls */}
      <div className="bg-white rounded-2xl shadow-lg border border-gray-100 p-6">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-xl flex items-center justify-center">
                <Filter className="w-5 h-5 text-white" />
              </div>
              <div>
                <h3 className="font-semibold text-gray-900">정렬 기준</h3>
                <p className="text-sm text-gray-500">원하는 기준으로 순위를 확인하세요</p>
              </div>
            </div>
          </div>
          
          <div className="relative">
            <select
              value={sortBy}
              onChange={(e) => setSortBy(e.target.value)}
              className="appearance-none bg-gradient-to-r from-blue-50 to-indigo-50 border-2 border-blue-200 rounded-2xl px-6 py-4 pr-12 text-sm font-semibold text-gray-800 focus:outline-none focus:ring-4 focus:ring-blue-100 focus:border-blue-400 transition-all duration-300 min-w-[240px] cursor-pointer hover:from-blue-100 hover:to-indigo-100 shadow-sm hover:shadow-md"
            >
              <option value="total">🏆 종합 순위</option>
              <option value="인적역량">👥 인적 역량</option>
              <option value="AI기술역량">🤖 AI 기술 역량</option>
              <option value="솔루션 역량">⚙️ 솔루션 역량</option>
            </select>
            
            {/* Custom dropdown arrow */}
            <div className="absolute inset-y-0 right-0 flex items-center pr-4 pointer-events-none">
              <div className="w-6 h-6 bg-gradient-to-br from-blue-500 to-indigo-600 rounded-lg flex items-center justify-center">
                <svg className="w-3 h-3 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M19 9l-7 7-7-7" />
                </svg>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

const ModernHeader = ({ totalMSPs, refreshing, needsRefresh, onRefresh }) => {
  return (
    <div className="relative mb-12">
      {/* Background with gradient */}
      <div className="absolute inset-0 bg-gradient-to-br from-blue-600 via-indigo-700 to-purple-800 rounded-3xl"></div>
      <div className="absolute inset-0 bg-black bg-opacity-20 rounded-3xl"></div>
      
      {/* Content */}
      <div className="relative p-8 md:p-12 text-white">
        <div className="max-w-4xl">
          {/* Top badge */}
          <div className="inline-flex items-center gap-2 bg-white bg-opacity-20 backdrop-blur-sm px-4 py-2 rounded-full text-sm font-medium mb-6">
            <Star className="w-4 h-4 text-yellow-300" />
            Naver Cloud Platform
          </div>
          
          {/* Main title */}
          <h1 className="text-4xl md:text-6xl font-bold mb-4 leading-tight">
            MSP 파트너
            <span className="block text-transparent bg-clip-text bg-gradient-to-r from-yellow-300 to-orange-300">
              순위표
            </span>
          </h1>
          
          {/* Subtitle */}
          <p className="text-xl md:text-2xl text-blue-100 mb-8 max-w-2xl leading-relaxed">
            AI 시대를 선도하는 클라우드 전문가들의 
            <span className="text-yellow-300 font-semibold"> 역량 평가 결과</span>를 확인하세요
          </p>
          
          {/* Stats row */}
          <div className="flex flex-wrap gap-6 md:gap-8 mb-8">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-white bg-opacity-20 backdrop-blur-sm rounded-xl flex items-center justify-center">
                <Users className="w-6 h-6 text-yellow-300" />
              </div>
              <div>
                <div className="text-2xl font-bold">{totalMSPs}</div>
                <div className="text-blue-200 text-sm">참여 파트너사</div>
              </div>
            </div>
            
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-white bg-opacity-20 backdrop-blur-sm rounded-xl flex items-center justify-center">
                <Target className="w-6 h-6 text-green-300" />
              </div>
              <div>
                <div className="text-2xl font-bold">3</div>
                <div className="text-blue-200 text-sm">평가 영역</div>
              </div>
            </div>
            
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-white bg-opacity-20 backdrop-blur-sm rounded-xl flex items-center justify-center">
                <Zap className="w-6 h-6 text-purple-300" />
              </div>
              <div>
                <div className="text-2xl font-bold">실시간</div>
                <div className="text-blue-200 text-sm">업데이트</div>
              </div>
            </div>
          </div>
          
          {/* Action button */}
          <button
            onClick={onRefresh}
            disabled={refreshing}
            className={`inline-flex items-center gap-3 px-6 py-3 rounded-xl font-semibold transition-all duration-300 ${
              needsRefresh 
                ? 'bg-gradient-to-r from-orange-500 to-red-500 hover:from-orange-600 hover:to-red-600 shadow-lg hover:shadow-xl text-white' 
                : 'bg-white bg-opacity-20 backdrop-blur-sm hover:bg-opacity-30 text-white border border-white border-opacity-30'
            } disabled:opacity-50 disabled:cursor-not-allowed transform hover:scale-105`}
          >
            <RefreshCw className={`w-5 h-5 ${refreshing ? 'animate-spin' : ''}`} />
            {refreshing ? '새로고침 중...' : needsRefresh ? '데이터 업데이트 필요' : '최신 데이터로 새로고침'}
          </button>
          
          {needsRefresh && (
            <div className="mt-4 inline-flex items-center gap-2 text-orange-300 text-sm">
              <div className="w-2 h-2 bg-orange-400 rounded-full animate-pulse"></div>
              새로운 평가 데이터가 감지되었습니다
            </div>
          )}
        </div>
        
        {/* Decorative elements */}
        <div className="absolute top-8 right-8 w-32 h-32 bg-white bg-opacity-10 rounded-full blur-3xl"></div>
        <div className="absolute bottom-8 right-16 w-24 h-24 bg-yellow-300 bg-opacity-20 rounded-full blur-2xl"></div>
      </div>
    </div>
  );
};

const ModernStatsGrid = ({ data }) => {
  const avgScore = data.length > 0 ? (data.reduce((sum, msp) => sum + msp.total_score, 0) / data.length) : 0;
  const maxScore = data.length > 0 ? Math.max(...data.map(msp => msp.total_score)) : 0;
  const topPerformer = data.length > 0 ? data[0]?.name : '';

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6 mb-12">
      <div className="bg-gradient-to-br from-blue-50 to-indigo-100 rounded-2xl p-6 border border-blue-200">
        <div className="flex items-center justify-between mb-4">
          <div className="w-12 h-12 bg-blue-500 rounded-xl flex items-center justify-center">
            <Users className="w-6 h-6 text-white" />
          </div>
          <div className="text-right">
            <div className="text-3xl font-bold text-blue-700">{data.length}</div>
            <div className="text-sm text-blue-600 font-medium">참여 파트너사</div>
          </div>
        </div>
        <div className="text-xs text-blue-600">전체 등록된 MSP 파트너</div>
      </div>
      
      <div className="bg-gradient-to-br from-green-50 to-emerald-100 rounded-2xl p-6 border border-green-200">
        <div className="flex items-center justify-between mb-4">
          <div className="w-12 h-12 bg-green-500 rounded-xl flex items-center justify-center">
            <TrendingUp className="w-6 h-6 text-white" />
          </div>
          <div className="text-right">
            <div className="text-3xl font-bold text-green-700">{avgScore.toFixed(1)}</div>
            <div className="text-sm text-green-600 font-medium">평균 점수</div>
          </div>
        </div>
        <div className="text-xs text-green-600">전체 파트너사 평균</div>
      </div>
      
      <div className="bg-gradient-to-br from-purple-50 to-violet-100 rounded-2xl p-6 border border-purple-200">
        <div className="flex items-center justify-between mb-4">
          <div className="w-12 h-12 bg-purple-500 rounded-xl flex items-center justify-center">
            <Star className="w-6 h-6 text-white" />
          </div>
          <div className="text-right">
            <div className="text-3xl font-bold text-purple-700">{maxScore.toFixed(1)}</div>
            <div className="text-sm text-purple-600 font-medium">최고 점수</div>
          </div>
        </div>
        <div className="text-xs text-purple-600">최우수 파트너사 점수</div>
      </div>
      
      <div className="bg-gradient-to-br from-orange-50 to-amber-100 rounded-2xl p-6 border border-orange-200">
        <div className="flex items-center justify-between mb-4">
          <div className="w-12 h-12 bg-orange-500 rounded-xl flex items-center justify-center">
            <Trophy className="w-6 h-6 text-white" />
          </div>
          <div className="text-right">
            <div className="text-2xl font-bold text-orange-700 truncate">{topPerformer}</div>
            <div className="text-sm text-orange-600 font-medium">1위 파트너사</div>
          </div>
        </div>
        <div className="text-xs text-orange-600">현재 선두 업체</div>
      </div>
    </div>
  );
};

// Main leaderboard page component
export default function LeaderboardPage() {
  const [data, setData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selectedMSP, setSelectedMSP] = useState(null);
  const [sortBy, setSortBy] = useState("total");
  const [refreshing, setRefreshing] = useState(false);
  const [refreshMessage, setRefreshMessage] = useState('');
  const [needsRefresh, setNeedsRefresh] = useState(false);

  const loadLeaderboard = async (showLoading = false) => {
    if (showLoading) setLoading(true);
    
    try {
      const response = await axios.get(`${API_BASE}/api/leaderboard`);
      setData(response.data);
    } catch (err) {
      console.error("Failed to load leaderboard", err);
    } finally {
      if (showLoading) setLoading(false);
    }
  };

  const checkRefreshStatus = async () => {
    try {
      // Check if there are any Unknown groups that need fixing
      const response = await axios.get(`${API_BASE}/api/debug_groups`);
      const hasUnknown = response.data.all_unique_groups.includes("Unknown") || 
                         response.data.all_unique_groups.includes("unknown");
      setNeedsRefresh(hasUnknown);
    } catch (err) {
      console.error("Failed to check refresh status", err);
    }
  };

  const handleRefresh = async () => {
    setRefreshing(true);
    setRefreshMessage('');
    
    try {
      // Call the public refresh endpoint
      const response = await axios.post(`${API_BASE}/api/refresh_leaderboard_public`);
      
      if (response.data.success) {
        setRefreshMessage(`✅ ${response.data.message}`);
        // Reload the leaderboard after refresh (no loading indicator)
        await loadLeaderboard(false);
        await checkRefreshStatus();
        
        // Clear message after 5 seconds
        setTimeout(() => setRefreshMessage(''), 5000);
      } else {
        setRefreshMessage(`❌ ${response.data.message}`);
      }
    } catch (err) {
      setRefreshMessage(`❌ 새로고침 실패: ${err.message}`);
    }
    
    setRefreshing(false);
  };

  useEffect(() => {
    loadLeaderboard(true); // Show loading on initial load
    checkRefreshStatus();
  }, []);

  // Sort the data based on selected criteria
  const sortedData = [...data].sort((a, b) => {
    if (sortBy === "total") {
      return b.total_score - a.total_score;
    } else {
      const scoreA = a.category_scores[sortBy] || 0;
      const scoreB = b.category_scores[sortBy] || 0;
      return scoreB - scoreA;
    }
  });

  // Loading state
  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-100 p-8">
        <div className="max-w-7xl mx-auto">
          <div className="text-center py-20">
            <div className="relative">
              <div className="animate-spin rounded-full h-16 w-16 border-4 border-blue-200 border-t-blue-600 mx-auto mb-6"></div>
              <div className="absolute inset-0 rounded-full bg-blue-100 blur-xl opacity-50"></div>
            </div>
            <p className="text-xl text-gray-600 font-medium">순위표를 불러오는 중...</p>
            <p className="text-sm text-gray-500 mt-2">잠시만 기다려주세요</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-indigo-100 p-4 md:p-8">
      <div className="max-w-7xl mx-auto">
        {/* Modern Header */}
        <ModernHeader 
          totalMSPs={data.length}
          refreshing={refreshing}
          needsRefresh={needsRefresh}
          onRefresh={handleRefresh}
        />

        {/* Modern Filter Controls */}
        <ModernFilterDropdown 
          sortBy={sortBy} 
          setSortBy={setSortBy}
          refreshMessage={refreshMessage}
        />

        {/* Modern Stats Grid */}
        <ModernStatsGrid data={sortedData} />

        {/* Leaderboard Grid */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {sortedData.map((msp, index) => (
            <MSPCard
              key={msp.name}
              msp={msp}
              rank={index + 1}
              onSelect={setSelectedMSP}
            />
          ))}
        </div>

        {/* Modal */}
        {selectedMSP && (
          <MSPModal msp={selectedMSP} onClose={() => setSelectedMSP(null)} />
        )}
      </div>
    </div>
  );
}
