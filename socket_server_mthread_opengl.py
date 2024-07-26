import socket
import threading
import time
import signal
import sys
import select
import glfw
from OpenGL.GL import *
from OpenGL.GLU import *
import numpy as np
from OpenGL.GL.shaders import compileProgram, compileShader
import glm

# 全局變量來控制程式運行
running = True
data_lock = threading.Lock()
point_cloud_data = []

# 添加着色器程序
vertex_shader = """
#version 330 core
layout (location = 0) in vec3 aPos;
layout (location = 1) in vec3 aColor;
out vec3 ourColor;
uniform mat4 mvp;

void main()
{
    gl_Position = mvp * vec4(aPos, 1.0);
    ourColor = aColor;
}
"""

fragment_shader = """
#version 330 core
in vec3 ourColor;
out vec4 FragColor;

void main()
{
    FragColor = vec4(ourColor, 1.0);
}
"""

# 初始化視角變數
camera_angle_x = -10
camera_angle_y = 0
camera_distance = 100

def signal_handler(sig, frame):
    global running
    print('\n程式正在結束，請稍候...')
    running = False

def update_point_cloud(new_points):
    global point_cloud_data
    with data_lock:
        point_cloud_data.extend(new_points)

def read_point_cloud():
    global point_cloud_data
    with data_lock:
        return list(point_cloud_data)

def receive_data(conn):
    global running
    conn.setblocking(0)  # 設置為非阻塞模式
    buffer = b''
    while running:
        ready = select.select([conn], [], [], 1)  # 等待1秒
        if ready[0]:
            try:
                data = conn.recv(24576 )#24576     8192
                if not data:
                    break
                buffer += data
                
                # 檢查是否收到完整的數據包（以'\n\n'為分隔符）
                while b'\n\n' in buffer:
                    packet, buffer = buffer.split(b'\n\n', 1)
                    decoded_packet = packet.decode().strip()
                    print(f"收到: {decoded_packet}")
                    
                    # 將接收到的數據拆分並存儲到列表中
                    new_points = []
                    for line in decoded_packet.split('\n'):
                        if line.strip():
                            try:
                                values = [float(x) for x in line.split()]
                                if len(values) == 6:  # 確保有 6 個值：x, y, z, r, g, b
                                    x, y, z, r, g, b = values
                                    new_points.append([x, y, z, r/255.0, g/255.0, b/255.0])  # 將 RGB 值轉換為 0-1 範圍
                            except ValueError as e:
                                print(f"數據解析錯誤: {e} - 錯誤行: {line}")
                    
                    update_point_cloud(new_points)
                    
                    # 回送收到的數據
                    conn.sendall(packet + b'\n\n')
            except (BlockingIOError, socket.error) as e:
                if e.errno != 10035:  # 忽略 "無法立即完成通訊端操作" 錯誤
                    print(f"接收數據時發生錯誤: {e}")
                    break
        time.sleep(0.05)  # 短暫休眠以減少 CPU 使用
    conn.close()

def prepare_vbo_vao(points):
    points_array = np.array(points, dtype=np.float32)
    
    vbo = glGenBuffers(1)
    glBindBuffer(GL_ARRAY_BUFFER, vbo)
    glBufferData(GL_ARRAY_BUFFER, points_array.nbytes, points_array, GL_DYNAMIC_DRAW)
    
    vao = glGenVertexArrays(1)
    glBindVertexArray(vao)
    glBindBuffer(GL_ARRAY_BUFFER, vbo)
    
    # 位置屬性
    glEnableVertexAttribArray(0)
    glVertexAttribPointer(0, 3, GL_FLOAT, GL_FALSE, 24, ctypes.c_void_p(0))
    # 顏色屬性
    glEnableVertexAttribArray(1)
    glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 24, ctypes.c_void_p(12))
    
    return vao, vbo

def draw_point_cloud(vao, point_count):
    glBindVertexArray(vao)
    glDrawArrays(GL_POINTS, 0, point_count)
    glBindVertexArray(0)

def draw_grid():
    glColor3f(0.5, 0.5, 0.5)  # 灰色
    glBegin(GL_LINES)
    for i in range(-10, 11):
        glVertex3f(i, 0, -10)
        glVertex3f(i, 0, 10)
        glVertex3f(-10, 0, i)
        glVertex3f(10, 0, i)
    glEnd()

def draw_axes():
    glBegin(GL_LINES)
    # X軸 - 紅色
    glColor3f(1, 0, 0)
    glVertex3f(-5, 0, 0)
    glVertex3f(5, 0, 0)
    # Y軸 - 綠色
    glColor3f(0, 1, 0)
    glVertex3f(0, -5, 0)
    glVertex3f(0, 5, 0)
    # Z軸 - 藍色
    glColor3f(0, 0, 1)
    glVertex3f(0, 0, -5)
    glVertex3f(0, 0, 5)
    glEnd()

def key_callback(window, key, scancode, action, mods):
    global camera_angle_x, camera_angle_y, camera_distance
    if action == glfw.PRESS or action == glfw.REPEAT:
        if key == glfw.KEY_UP:
            camera_angle_x -= 5
        elif key == glfw.KEY_DOWN:
            camera_angle_x += 5
        elif key == glfw.KEY_LEFT:
            camera_angle_y -= 5
        elif key == glfw.KEY_RIGHT:
            camera_angle_y += 5
        elif key == glfw.KEY_W:
            camera_distance -= 2
        elif key == glfw.KEY_S:
            camera_distance += 2

def start_server():
    global running
    host = '127.0.0.1'
    port = 65432

    # 初始化 GLFW
    if not glfw.init():
        print("無法初始化 GLFW")
        return

    # 創建窗口
    window = glfw.create_window(640, 480, "Point Cloud Visualization", None, None)
    if not window:
        glfw.terminate()
        print("無法創建 GLFW 窗口")
        return

    glfw.make_context_current(window)
    glfw.set_key_callback(window, key_callback)

    # 編譯着色器程序
    shader = compileProgram(
        compileShader(vertex_shader, GL_VERTEX_SHADER),
        compileShader(fragment_shader, GL_FRAGMENT_SHADER)
    )

    # 初始化 VBO 和 VAO
    vao, vbo = prepare_vbo_vao([])

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind((host, port))
        s.listen()
        s.setblocking(False)  # 設置為非阻塞模式
        print(f"服務器正在監聽 {host}:{port}")
        print("按 Ctrl+C 來停止服務器")
        
        while running and not glfw.window_should_close(window):
            try:
                ready = select.select([s], [], [], 0.01)  # 等待0.01秒
                if ready[0]:
                    conn, addr = s.accept()
                    print(f"已連接到 {addr}")
                    
                    # 為每個連接創建一個新線程
                    client_thread = threading.Thread(target=receive_data, args=(conn,))
                    client_thread.daemon = True
                    client_thread.start()
                
                # 渲染點雲
                glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
                glUseProgram(shader)

                # 計算攝像機位置
                camera_x = camera_distance * np.sin(np.radians(camera_angle_y)) * np.cos(np.radians(camera_angle_x))
                camera_y = camera_distance * np.sin(np.radians(camera_angle_x))
                camera_z = camera_distance * np.cos(np.radians(camera_angle_y)) * np.cos(np.radians(camera_angle_x))

                # 計算 MVP 矩陣
                projection = glm.perspective(glm.radians(45), 640/480, 0.1, 1000.0)
                view = glm.lookAt(glm.vec3(camera_x, camera_y, camera_z), glm.vec3(0, 0, 0), glm.vec3(0, 1, 0))
                model = glm.mat4(1.0)
                mvp = projection * view * model

                # 將 MVP 矩陣傳遞給著色器
                mvpLoc = glGetUniformLocation(shader, "mvp")
                glUniformMatrix4fv(mvpLoc, 1, GL_FALSE, glm.value_ptr(mvp))

                # 設置 OpenGL 狀態
                glEnable(GL_POINT_SMOOTH)
                glEnable(GL_PROGRAM_POINT_SIZE)
                glPointSize(3.0)
                glEnable(GL_DEPTH_TEST)
                glDepthFunc(GL_LESS)

                # 禁用不需要的功能
                glDisable(GL_LIGHTING)
                glDisable(GL_COLOR_MATERIAL)

                draw_grid()
                draw_axes()

                # 更新點雲數據
                points = read_point_cloud()
                if points:
                    points_array = np.array(points, dtype=np.float32)
                    glBindBuffer(GL_ARRAY_BUFFER, vbo)
                    glBufferData(GL_ARRAY_BUFFER, points_array.nbytes, points_array, GL_DYNAMIC_DRAW)
                    draw_point_cloud(vao, len(points))

                glUseProgram(0)
                glfw.swap_buffers(window)
                glfw.poll_events()
                
            except (BlockingIOError, socket.error) as e:
                if e.errno != 10035:  # 忽略 "無法立即完成通訊端操作" 錯誤
                    print(f"接受連接時發生錯誤: {e}")
            
        print("正在關閉服務器...")
        s.close()

    glfw.terminate()

if __name__ == "__main__":
    # 設置信號處理器
    signal.signal(signal.SIGINT, signal_handler)
    
    start_server()
    
    print("服務器已關閉")