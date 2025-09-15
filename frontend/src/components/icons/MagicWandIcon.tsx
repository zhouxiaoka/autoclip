import React from 'react';

interface MagicWandIconProps {
  className?: string;
  style?: React.CSSProperties;
}

const MagicWandIcon: React.FC<MagicWandIconProps> = ({ className, style }) => {
  return (
    <svg
      width="16"
      height="16"
      viewBox="0 0 16 16"
      fill="none"
      xmlns="http://www.w3.org/2000/svg"
      className={className}
      style={style}
    >
      {/* 魔法棒主体 - 白色对角线 */}
      <path
        d="M2 14L14 2"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
      />
      {/* 魔法棒顶部 - 小菱形 */}
      <path
        d="M12 2L14 4L12 6L10 4L12 2Z"
        fill="currentColor"
      />
      {/* 左上角星星 */}
      <path
        d="M3 3L3.5 4.5L5 4.5L3.5 5.5L4 7L3 6L2 7L2.5 5.5L1 4.5L2.5 4.5L3 3Z"
        fill="#87CEEB"
      />
      {/* 右下角星星 */}
      <path
        d="M13 13L13.5 14.5L15 14.5L13.5 15.5L14 17L13 16L12 17L12.5 15.5L11 14.5L12.5 14.5L13 13Z"
        fill="#87CEEB"
      />
    </svg>
  );
};

export default MagicWandIcon;

