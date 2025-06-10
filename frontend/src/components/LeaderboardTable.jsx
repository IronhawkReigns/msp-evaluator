import React from "react";

export default function LeaderboardTable({ data, onSelect }) {
  return (
    <div className="overflow-x-auto shadow border rounded-lg">
      <table className="min-w-full table-auto text-sm">
        <thead className="bg-gray-100 text-left">
          <tr>
            <th className="px-4 py-2">#</th>
            <th className="px-4 py-2">MSP</th>
            <th className="px-4 py-2 text-center">총점</th>
            <th className="px-4 py-2 text-center">인적역량</th>
            <th className="px-4 py-2 text-center">AI기술역량</th>
            <th className="px-4 py-2 text-center">솔루션 역량</th>
          </tr>
        </thead>
        <tbody>
          {data.map((msp, index) => (
            <tr
              key={msp.name}
              className="border-t hover:bg-gray-50 cursor-pointer"
              onClick={() => onSelect(msp)}
            >
              <td className="px-4 py-2">{index + 1}</td>
              <td className="px-4 py-2 font-medium">{msp.name}</td>
              <td className="px-4 py-2 text-center">{msp.total_score}</td>
              <td className="px-4 py-2 text-center">{msp.category_scores["인적역량"] || "-"}</td>
              <td className="px-4 py-2 text-center">{msp.category_scores["AI기술역량"] || "-"}</td>
              <td className="px-4 py-2 text-center">{msp.category_scores["솔루션 역량"] || "-"}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
