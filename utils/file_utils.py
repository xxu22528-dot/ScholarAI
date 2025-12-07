# utils/file_utils.py
import base64
from langchain_community.document_loaders import PyPDFLoader

def extract_text_from_pdf(uploaded_file) -> str:
    """
    从 Streamlit 的 UploadedFile 对象中提取文本
    """
    try:
        # Streamlit 的上传文件是内存对象，LangChain 通常需要文件路径
        # 所以我们先把它保存为临时文件
        temp_filename = f"temp_{uploaded_file.name}"
        with open(temp_filename, "wb") as f:
            f.write(uploaded_file.getbuffer())
            
        # 使用 LangChain 加载 PDF
        loader = PyPDFLoader(temp_filename)
        pages = loader.load()
        
        # 提取所有页面的文本
        full_text = "\n\n".join([page.page_content for page in pages])
        return full_text
        
    except Exception as e:
        return f"PDF 解析失败: {str(e)}"

def encode_image_to_base64(uploaded_file) -> str:
    """
    将图片文件转为 Base64 字符串 (供 AI 视觉分析使用)
    """
    try:
        bytes_data = uploaded_file.getvalue()
        return base64.b64encode(bytes_data).decode('utf-8')
    except Exception as e:
        print(f"图片转码失败: {e}")
        return ""