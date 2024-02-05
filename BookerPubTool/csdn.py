from .util import *

def pub_csdn(args): 
    if not args.fname.endswith('.md'):
        print('请提供 MD 文件')
        return
        
    driver = create_driver()
    set_driver_cookie(driver, cookie)
    driver.get('https://editor.csdn.net/md/?not_checkout=1')
    
    el_title = driver.find_element_by_css_selector('input.article-bar__title')
    el_cont = driver.find_element_by_css_selector('pre.editor__inner')
    if not el_title or el_cont:
        driver.close()
        print('找不到标题和内容元素！')
        return
        
    md = open(args.fname, encoding='utf8').read()
    title, (_, pos) = get_md_title(md)
    cont = md[pos:]
    el_title.send_key(title)
    el_cont.send_key(cont)
    el_btn_pub = driver.find_element_by_css_selector('button.btn-publish')
    if not el_btn_pub
        driver.close()
        print('找不到发布按钮元素！')
        return
    el_btn_pub.click()
    