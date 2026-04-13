# Project Goal

Build a modern, professional English study webpage with interactive flip-card word cards and integrated YouTube video.

Create a comprehensive learning platform with advanced word card functionality that mimics professional language learning apps.

# Input Data Structure

The script expects files directly in the `data` folder:
- data/00_meta.txt (must include video_url and video_id)
- data/01_intro.txt  
- data/02_core.txt
- data/03_summary.txt
- data/04_full_script.txt
- data/05_wordcard.txt

# Required Output Files

Create these files in the current working directory:
- index.html (modern study page with flip-card word cards)
- style.css (Tailwind + custom flip card animations)
- script.js (flip card interactions + enhanced functionality)

# Enhanced Word Cards Requirements

## Interactive Flip Card Design

### Front Side (Default View)
- Large, prominent headword display
- Small speaker icon in top-right corner
- Subtle "Click to flip" instruction
- Clean, minimalist design
- Hover effects for interactivity

### Back Side (Detailed View)
- **Row 1:** Part of speech + Korean meaning (품사 | 한글 뜻)
- **Row 2:** English definition + TTS button (영영사전 + 🔊)
- **Row 3:** Korean literal translation (한글 직역)
- **Row 4:** English example sentence + TTS button (영어 예문 + 🔊)
- **Row 5:** Korean example translation (예문 한글 직역)
- Click anywhere to flip back

## Flip Animation Requirements

### CSS Flip Animation
```css
.word-card {
  perspective: 1000px;
  height: 280px;
  transition: transform 0.6s;
  transform-style: preserve-3d;
}

.word-card.flipped {
  transform: rotateY(180deg);
}

.card-front, .card-back {
  position: absolute;
  width: 100%;
  height: 100%;
  backface-visibility: hidden;
  border-radius: 12px;
  padding: 20px;
}

.card-back {
  transform: rotateY(180deg);
}
Smooth Transitions
0.6s duration for flip animation
Easing function for natural feel
Preserve-3d for realistic effect
Backface-visibility hidden for clean flip
Word Card Layout StructureGrid Layout<div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
  <!-- Word cards here -->
</div>
Individual Card Structure<div class="word-card cursor-pointer" onclick="flipCard(this)">
  <!-- Front Side -->
  <div class="card-front bg-white border border-gray-200 shadow-lg">
    <div class="flex justify-between items-start mb-4">
      <h3 class="text-2xl font-bold text-gray-800">headword</h3>
      <button class="tts-btn-small" onclick="playWordTTS(event, 'headword')">🔊</button>
    </div>
    <p class="text-gray-500 text-center mt-8">클릭하여 뒤집기</p>
  </div>
  
  <!-- Back Side -->
  <div class="card-back bg-gradient-to-br from-blue-50 to-indigo-50 border border-indigo-200 shadow-lg">
    <!-- Row 1: Part of speech + Korean meaning -->
    <div class="flex justify-between items-center mb-3 pb-2 border-b border-indigo-200">
      <span class="text-sm font-bold text-indigo-600 bg-indigo-100 px-2 py-1 rounded">noun</span>
      <span class="text-sm font-bold text-gray-700">의미: 갈등</span>
    </div>
    
    <!-- Row 2: English definition + TTS -->
    <div class="flex justify-between items-start mb-3">
      <p class="text-sm text-gray-800 font-medium flex-1">a serious disagreement or fighting between groups</p>
      <button class="tts-btn-small ml-2" onclick="playDefinitionTTS(event, 'definition_text')">🔊</button>
    </div>
    
    <!-- Row 3: Korean literal translation -->
    <div class="mb-3">
      <p class="text-xs text-gray-600">직역: 집단들 사이의 심각한 불일치 또는 싸움</p>
    </div>
    
    <!-- Row 4: English example + TTS -->
    <div class="flex justify-between items-start mb-2">
      <p class="text-sm text-gray-800 italic flex-1">This return to conflict made the lives of many people very hard.</p>
      <button class="tts-btn-small ml-2" onclick="playExampleTTS(event, 'example_text')">🔊</button>
    </div>
    
    <!-- Row 5: Korean example translation -->
    <div>
      <p class="text-xs text-gray-600">예문 직역: 이러한 분쟁으로의 복귀는 많은 사람들의 삶을 매우 어렵게 만들었다.</p>
    </div>
  </div>
</div>
Word Card Data ProcessingExpected 05_wordcard.txt Format[Card 1]
headword: conflict
part_of_speech: noun
meaning_kr: 갈등
definition_en: a serious disagreement or fighting between groups or countries
definition_kr_literal: 집단들이나 나라들 사이의 심각한 불일치 또는 싸움
example_en: This return to conflict made the lives of many people very hard
example_kr_literal: 이러한 분쟁으로의 복귀는 많은 사람들의 삶을 매우 어렵게 만들었다

[Card 2]
headword: tension
part_of_speech: noun
meaning_kr: 긴장
definition_en: a nervous or difficult situation between people, groups, or countries
definition_kr_literal: 사람들, 집단들, 또는 나라들 사이의 긴장되거나 어려운 상황
example_en: This creates tension and can lead to conflict
example_kr_literal: 이것은 긴장을 만들고 분쟁으로 이어질 수 있다
Interactive FeaturesClick Handlersfunction flipCard(cardElement) {
  cardElement.classList.toggle('flipped');
}

function playWordTTS(event, word) {
  event.stopPropagation(); // Prevent card flip
  speakEnglish(word);
}

function playDefinitionTTS(event, definition) {
  event.stopPropagation();
  speakEnglish(definition);
}

function playExampleTTS(event, example) {
  event.stopPropagation();
  speakEnglish(example);
}
Enhanced TTS Integration
Prevent card flip when clicking TTS buttons
Multiple TTS functions for different content types
Consistent voice settings across all cards
Visual feedback during speech playback
Visual Design EnhancementColor Coding
Front cards: Clean white background with subtle shadows
Back cards: Gradient blue background for distinction
TTS buttons: Consistent small circular design
Text hierarchy: Clear font weights and sizes
Responsive Grid
1 column on mobile (< 768px)
2 columns on tablet (768px - 1024px)
3 columns on desktop (> 1024px)
Consistent card heights across row
Hover Effects.word-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 10px 25px rgba(0,0,0,0.1);
}

.tts-btn-small:hover {
  background-color: rgba(59, 130, 246, 0.1);
  transform: scale(1.1);
}
Accessibility Features
Keyboard navigation support (Space/Enter to flip)
Screen reader friendly labels
High contrast text ratios
Touch-friendly button sizes (minimum 44px)
Focus indicators for all interactive elements
Performance Considerations
CSS transforms for smooth animations
Event delegation for efficient memory usage
Lazy loading for large word sets
Debounced flip animations to prevent spam clicking
Success Criteria for Word CardsThe enhanced word cards should:
✅ Flip smoothly with realistic 3D animation
✅ Display all required information in organized layout
✅ Provide multiple TTS options (word, definition, example)
✅ Prevent accidental flips when using TTS buttons
✅ Work seamlessly across all device sizes
✅ Feel like professional flashcard apps (Anki, Quizlet level)
✅ Load quickly and respond smoothly to interactions
The word cards should be the standout feature that makes users want to study with this platform regularly.