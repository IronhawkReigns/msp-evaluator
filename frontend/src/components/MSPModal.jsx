import React from "react";

export default function MSPModal({ msp, onClose }) {
  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex justify-center items-center z-50">
      <div className="bg-white p-6 rounded shadow-lg w-full max-w-lg relative">
        <button
          onClick={onClose}
          className="absolute top-2 right-2 text-gray-500 hover:text-black text-lg"
        >
          ×
        </button>
        <h2 className="text-2xl font-bold mb-4">{msp.name}</h2>
        <p className="mb-2">
          <strong>총점:</strong> {msp.total_score}
        </p>
        <div className="mb-2">
          <strong>카테고리 점수:</strong>
          <ul className="list-disc list-inside ml-2">
            {Object.entries(msp.category_scores || {}).map(([category, score]) => (
              <li key={category}>
                {category}: {score}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}