import { t } from '../i18n'
import { useTranslation } from 'react-i18next'
import React from 'react'
import { VideoCategory } from '../services/api'
import { categoryOptions } from '../utils/videoCategories'

interface VideoCategoryPickerProps {
  categories: VideoCategory[] | null | undefined
  selectedCategory: string
  onSelect: (value: string) => void
}

const VideoCategoryPicker: React.FC<VideoCategoryPickerProps> = ({
  categories,
  selectedCategory,
  onSelect,
}) => {
  useTranslation()
  const options = categoryOptions(categories)

  return (
    <div style={{
      display: 'flex',
      flexWrap: 'wrap',
      gap: '8px'
    }}>
      {options.map(category => {
        const isSelected = selectedCategory === category.value
        return (
          <div
            key={category.value}
            onClick={() => onSelect(category.value)}
            style={{
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              padding: '8px 12px',
              borderRadius: '6px',
              border: isSelected
                ? `2px solid ${category.color}`
                : '2px solid var(--ac-line)',
              background: isSelected
                ? `${category.color}25`
                : 'var(--ac-line)',
              color: isSelected ? '#ffffff' : 'rgba(255, 255, 255, 0.8)',
              boxShadow: isSelected
                ? `0 0 12px ${category.color}40`
                : 'none',
              cursor: 'pointer',
              transition: 'all 0.2s ease',
              fontSize: '13px',
              fontWeight: isSelected ? 600 : 400,
              userSelect: 'none'
            }}
            onMouseEnter={(e) => {
              if (!isSelected) {
                e.currentTarget.style.background = 'var(--ac-line)'
                e.currentTarget.style.borderColor = 'rgba(255, 255, 255, 0.2)'
              }
            }}
            onMouseLeave={(e) => {
              if (!isSelected) {
                e.currentTarget.style.background = 'var(--ac-line)'
                e.currentTarget.style.borderColor = 'var(--ac-line)'
              }
            }}
          >
            <span style={{ fontSize: '14px' }}>{category.icon}</span>
            <span>{t(category.name)}</span>
          </div>
        )
      })}
    </div>
  )
}

export default VideoCategoryPicker
