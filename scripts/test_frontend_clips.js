// 测试前端切片API调用
const axios = require('axios');

const api = axios.create({
  baseURL: 'http://localhost:8000/api/v1',
  timeout: 300000,
  headers: {
    'Content-Type': 'application/json',
  },
});

// 响应拦截器
api.interceptors.response.use(
  (response) => {
    return response.data;
  },
  (error) => {
    console.error('API Error:', error);
    return Promise.reject(error);
  }
);

async function testClipsAPI() {
  const projectId = '1fdb0bf1-7f3c-44f7-a69d-90c5a1d26fbe';
  
  try {
    console.log('🧪 测试前端切片API调用...');
    
    // 模拟前端API调用
    const response = await api.get(`/clips/?project_id=${projectId}`);
    const clips = response.items || response || [];
    
    console.log(`✅ 原始API响应: ${clips.length} 个切片`);
    
    // 模拟前端数据转换
    const convertedClips = clips.map((clip) => {
      // 转换秒数为时间字符串格式
      const formatSecondsToTime = (seconds) => {
        const hours = Math.floor(seconds / 3600);
        const minutes = Math.floor((seconds % 3600) / 60);
        const secs = Math.floor(seconds % 60);
        return `${hours.toString().padStart(2, '0')}:${minutes.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
      };
      
      // 获取metadata中的内容
      const metadata = clip.clip_metadata || {};
      
      return {
        id: clip.id,
        title: clip.title,
        generated_title: clip.title,
        start_time: formatSecondsToTime(clip.start_time),
        end_time: formatSecondsToTime(clip.end_time),
        final_score: clip.score || 0,
        recommend_reason: metadata.recommend_reason || clip.description || '',
        outline: metadata.outline || clip.description || '',
        content: metadata.content || [clip.description || ''],
        chunk_index: metadata.chunk_index || 0
      };
    });
    
    console.log(`✅ 转换后的切片: ${convertedClips.length} 个`);
    
    if (convertedClips.length > 0) {
      const firstClip = convertedClips[0];
      console.log('📋 第一个切片详情:');
      console.log(`   ID: ${firstClip.id}`);
      console.log(`   标题: ${firstClip.title}`);
      console.log(`   时间: ${firstClip.start_time} - ${firstClip.end_time}`);
      console.log(`   分数: ${firstClip.final_score}`);
      console.log(`   推荐理由: ${firstClip.recommend_reason.substring(0, 50)}...`);
      console.log(`   内容要点: ${firstClip.content.length} 个`);
    }
    
    return convertedClips;
    
  } catch (error) {
    console.error('❌ API调用失败:', error.message);
    if (error.response) {
      console.error('   状态码:', error.response.status);
      console.error('   响应数据:', error.response.data);
    }
    return [];
  }
}

testClipsAPI().then(clips => {
  console.log(`\n🎉 测试完成，返回 ${clips.length} 个切片`);
}).catch(error => {
  console.error('❌ 测试失败:', error);
});

