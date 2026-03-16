/**
 * JavaScript SDK 使用示例
 */

// 初始化客户端
const client = new ModelSpeedTest({
  baseUrl: 'http://localhost:15010',
  apiKey: 'your-api-key' // 可选
});

async function main() {
  // 1. 获取配置
  console.log('=== 获取配置 ===');
  const config = await client.getConfig();
  console.log(`模型数量: ${config.models?.length || 0}`);
  console.log(`测试用例数量: ${config.test_cases?.length || 0}`);

  // 2. 添加模型
  console.log('\n=== 添加模型 ===');
  const newModel = await client.addModel({
    name: 'GPT-4',
    endpoint: 'https://api.openai.com/v1/chat/completions',
    api_key: 'sk-xxx',
    model: 'gpt-4',
    provider: 'openai',
    enabled: true
  });
  console.log('添加模型结果:', newModel);

  // 3. 启动测试
  console.log('\n=== 启动测试 ===');
  const result = await client.startTest({
    models: ['MiniMax-M2.5-HighSpeed'],
    cases: ['tc_ontology_1'],
    testRounds: 5
  });
  console.log('启动结果:', result);

  // 4. 监听事件流
  console.log('\n=== 监听事件 ===');
  
  // 监听进度事件
  client.on('progress', (data) => {
    console.log('进度:', data.data);
  });
  
  // 监听完成事件
  client.on('complete', (data) => {
    console.log('完成:', data.data);
  });
  
  // 监听错误事件
  client.on('error', (data) => {
    console.error('错误:', data.data);
  });
  
  // 连接事件流
  client.connectEvents();

  // 5. 获取状态
  console.log('\n=== 获取状态 ===');
  const status = await client.getStatus();
  console.log('测试状态:', status);

  // 6. 获取历史
  console.log('\n=== 获取历史 ===');
  const history = await client.getHistory({ limit: 10 });
  console.log('历史记录:', history);

  // 7. 配置 Webhook
  console.log('\n=== 配置 Webhook ===');
  const webhook = await client.configureWebhook({
    url: 'https://your-server.com/webhook',
    events: ['test_complete', 'test_error'],
    enabled: true,
    secret: 'your-secret'
  });
  console.log('Webhook 配置:', webhook);

  // 8. 停止测试
  console.log('\n=== 停止测试 ===');
  const stopResult = await client.stopTest();
  console.log('停止结果:', stopResult);

  // 断开事件连接
  client.disconnectEvents();
}

// 运行示例
main().catch(console.error);