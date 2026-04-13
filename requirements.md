# Project Goal

Build a modern, professional English study webpage with comprehensive navigation system, interactive flip-card word cards, and integrated YouTube video.

Create a complete learning platform that seamlessly connects with the main hub and provides excellent user experience.

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
- index.html (complete study page with navigation)
- style.css (Tailwind + custom styles + navigation)
- script.js (full functionality + navigation handlers)

# Navigation System Requirements

## Header Navigation
Create a comprehensive header with the following elements:

### Brand Section
- Logo: 🎓 icon in gradient circle
- Title: "English Study Hub"
- Subtitle: "쉐도잉과 암기를 위한 영어 학습"

### Navigation Buttons
- **홈으로 버튼**: Links to `../../../../index.html`
- **다른 콘텐츠 드롭다운**: Shows available content by level
- **모바일 메뉴**: Hamburger menu for mobile devices

### Breadcrumb Navigation
Display hierarchical navigation:
`홈 > 듣기 연습 > Level X > [Content Title]`

## Footer Navigation
- Prominent "메인으로 돌아가기" button
- Site description and copyright
- Additional quick links

# Page Layout Structure

```html
<!DOCTYPE html>
<html lang="ko">
<head>
    <!-- Meta tags, Tailwind CSS, custom styles -->
</head>
<body class="bg-gray-50 min-h-screen">

    <!-- Sticky Navigation Header -->
    <header class="bg-white shadow-lg border-b-2 border-indigo-200 sticky top-0 z-50">
        <!-- Navigation content -->
    </header>

    <!-- Breadcrumb -->
    <div class="bg-gray-100 border-b border-gray-200">
        <!-- Breadcrumb navigation -->
    </div>

    <!-- Main Content Container -->
    <main class="max-w-7xl mx-auto px-4 py-6">
        
        <!-- Video Section -->
        <section class="mb-8">
            <!-- YouTube embedded player -->
        </section>

        <!-- Page Title & Meta -->
        <section class="mb-8">
            <!-- Title, level, source info -->
        </section>

        <!-- Tab Navigation -->
        <nav class="mb-8">
            <!-- Tab buttons -->
        </nav>

        <!-- Content Area -->
        <section class="mb-12">
            <!-- All tab content -->
        </section>

    </main>

    <!-- Footer Navigation -->
    <footer class="bg-white border-t border-gray-200">
        <!-- Footer content with back button -->
    </footer>

</body>
</html>
Detailed Navigation ImplementationSticky Header HTML Structure<header class="bg-white shadow-lg border-b-2 border-indigo-200 sticky top-0 z-50">
    <div class="max-w-7xl mx-auto px-4 py-4">
        <div class="flex items-center justify-between">
            <!-- Logo/Brand Section -->
            <div class="flex items-center space-x-3">
                <div class="w-10 h-10 bg-gradient-to-br from-indigo-500 to-purple-600 rounded-lg flex items-center justify-center">
                    <span class="text-white font-bold text-lg">🎓</span>
                </div>
                <div>
                    <h1 class="text-xl font-bold text-gray-800">English Study Hub</h1>
                    <p class="text-xs text-gray-500">쉐도잉과 암기를 위한 영어 학습</p>
                </div>
            </div>
            
            <!-- Desktop Navigation -->
            <nav class="hidden md:flex items-center space-x-4">
                <a href="../../../../index.html" 
                   class="flex items-center space-x-2 px-4 py-2 bg-indigo-100 text-indigo-700 rounded-lg hover:bg-indigo-200 transition-colors">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"></path>
                    </svg>
                    <span class="font-semibold">홈으로</span>
                </a>
                
                <!-- Dropdown Menu -->
                <div class="relative group">
                    <button class="flex items-center space-x-2 px-4 py-2 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path>
                        </svg>
                        <span>다른 콘텐츠</span>
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"></path>
                        </svg>
                    </button>
                    
                    <!-- Dropdown Content -->
                    <div class="absolute right-0 mt-2 w-56 bg-white rounded-lg shadow-lg border border-gray-200 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 z-50">
                        <div class="py-2">
                            <div class="px-3 py-2 text-xs font-semibold text-gray-500 border-b border-gray-200">Level 1 - 기초</div>
                            <a href="#" class="block px-4 py-2 text-sm text-gray-400 cursor-not-allowed">준비 중...</a>
                            
                            <div class="px-3 py-2 text-xs font-semibold text-gray-500 border-b border-gray-200 mt-1">Level 2 - 중급</div>
                            <a href="#" class="block px-4 py-2 text-sm text-gray-400 cursor-not-allowed">준비 중...</a>
                            
                            <div class="px-3 py-2 text-xs font-semibold text-gray-500 border-b border-gray-200 mt-1">Level 3 - 고급</div>
                            <a href="../../../../index.html#levels" class="block px-4 py-2 text-sm text-indigo-600 font-semibold hover:bg-indigo-50">다른 Level 3 콘텐츠 보기</a>
                        </div>
                    </div>
                </div>
            </nav>
            
            <!-- Mobile Menu Button -->
            <button id="mobile-menu-btn" class="md:hidden p-2 rounded-lg bg-gray-100 text-gray-700 hover:bg-gray-200 transition-colors">
                <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"></path>
                </svg>
            </button>
        </div>
        
        <!-- Mobile Menu (Hidden by default) -->
        <div id="mobile-menu" class="md:hidden mt-4 pb-4 border-t border-gray-200 hidden">
            <div class="space-y-2 pt-4">
                <a href="../../../../index.html" class="block px-4 py-3 text-gray-700 hover:bg-gray-100 rounded-lg transition-colors">
                    🏠 홈으로 돌아가기
                </a>
                <a href="../../../../index.html#levels" class="block px-4 py-3 text-gray-700 hover:bg-gray-100 rounded-lg transition-colors">
                    📚 다른 학습 콘텐츠
                </a>
            </div>
        </div>
    </div>
</header>
Breadcrumb Navigation<div class="bg-gray-100 border-b border-gray-200">
    <div class="max-w-7xl mx-auto px-4 py-3">
        <nav class="flex items-center space-x-2 text-sm">
            <a href="../../../../index.html" class="text-indigo-600 hover:text-indigo-800 font-medium">홈</a>
            <svg class="w-4 h-4 text-gray-400" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd"></path>
            </svg>
            <span class="text-gray-500">듣기 연습</span>
            <svg class="w-4 h-4 text-gray-400" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd"></path>
            </svg>
            <span class="text-gray-500" id="breadcrumb-level">Level 3</span>
            <svg class="w-4 h-4 text-gray-400" fill="currentColor" viewBox="0 0 20 20">
                <path fill-rule="evenodd" d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z" clip-rule="evenodd"></path>
            </svg>
            <span class="text-gray-800 font-medium" id="breadcrumb-title">Loading...</span>
        </nav>
    </div>
</div>
Footer Navigation<footer class="bg-white border-t border-gray-200 mt-12">
    <div class="max-w-7xl mx-auto px-4 py-8">
        <div class="flex flex-col md:flex-row items-center justify-between">
            <!-- Back to Main Button -->
            <div class="mb-6 md:mb-0">
                <a href="../../../../index.html" 
                   class="inline-flex items-center space-x-3 px-8 py-4 bg-gradient-to-r from-indigo-500 to-purple-600 text-white font-bold rounded-xl hover:from-indigo-600 hover:to-purple-700 transition-all shadow-lg transform hover:scale-105">
                    <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-6 0a1 1 0 001-1v-4a1 1 0 011-1h2a1 1 0 011 1v4a1 1 0 001 1m-6 0h6"></path>
                    </svg>
                    <span>메인으로 돌아가기</span>
                </a>
            </div>
            
            <!-- Site Info -->
            <div class="text-center md:text-right">
                <p class="text-gray-600 mb-2">영어 학습의 새로운 경험을 만나보세요</p>
                <p class="text-sm text-gray-500">© 2024 English Study Hub. Made with ❤️</p>
            </div>
        </div>
        
        <!-- Additional Links -->
        <div class="mt-8 pt-6 border-t border-gray-200 text-center">
            <div class="flex flex-wrap justify-center gap-6 text-sm text-gray-500">
                <a href="../../../../index.html#guide" class="hover:text-indigo-600 transition-colors">사용법</a>
                <span>|</span>
                <a href="../../../../index.html#levels" class="hover:text-indigo-600 transition-colors">다른 콘텐츠</a>
                <span>|</span>
                <a href="../../../../index.html" class="hover:text-indigo-600 transition-colors">홈페이지</a>
            </div>
        </div>
    </div>
</footer>