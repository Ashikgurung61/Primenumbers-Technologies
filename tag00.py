import time
import pandas as pd
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, NoSuchElementException, ElementClickInterceptedException, StaleElementReferenceException
import re

def setup_driver():
    """Set up and return a Chrome WebDriver with headless options."""
    chrome_options = Options()
    chrome_options.add_argument("--headless") 
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920,1080") 
    chrome_options.add_argument("--start-maximized")  
    chrome_options.add_argument("--disable-notifications") 
    
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=chrome_options)
    return driver

def handle_popup(driver):
    """Handle the popup that appears when the page loads."""
    try:
        ok_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "button.swal2-confirm.swal2-styled"))
        )
        print("Found popup, clicking OK button")
        ok_button.click()
        time.sleep(1)  
        return True
    except (TimeoutException, NoSuchElementException) as e:
        print("No popup found or could not close popup")
        return False

def safe_get_element_text(driver, xpath, wait_time=10, default="Not found"):
    """Safely get the text of an element with error handling."""
    try:
        element = WebDriverWait(driver, wait_time).until(
            EC.presence_of_element_located((By.XPATH, xpath))
        )
        return element.text.strip() if element.text else default
    except (TimeoutException, NoSuchElementException) as e:
        print(f"Element not found: {xpath} - {str(e)}")
        return default

def get_project_id_from_element(project_element):
    """Extract project ID from the project element if possible."""
    try:
        for attr in ['data-id', 'id', 'data-project-id']:
            project_id = project_element.get_attribute(attr)
            if project_id:
                return project_id
        
        view_details_link = project_element.find_element(By.TAG_NAME, "a")
        href = view_details_link.get_attribute('href')
        if href:
            match = re.search(r'id=(\d+)', href)
            if match:
                return match.group(1)
    except:
        pass
    
    import random
    return f"project_{random.randint(1000, 9999)}"

def scrape_project_details(driver, project_element, project_index):
    """Scrape the details of a project directly from the element or by clicking on it."""
    try:
        project_id = get_project_id_from_element(project_element)
        print(f"Processing project {project_index} with ID: {project_id}")
        
        view_buttons = []
        for selector in [
            ".//a[contains(text(), 'View Details')]", 
            ".//a[contains(@class, 'btn-primary') and contains(text(), 'View Details')]",
            ".//a[contains(text(), 'details')]",
            ".//a[contains(@class, 'btn')]",
            ".//button[contains(text(), 'View')]"
        ]:
            try:
                buttons = project_element.find_elements(By.XPATH, selector)
                view_buttons.extend(buttons)
            except:
                continue
        
        if not view_buttons:
            print(f"No view details button found for project {project_index}")
            try:
                print("Attempting to extract data from project card directly")
                rera_no = project_element.find_element(By.CSS_SELECTOR, "span.fw-bold").text.strip()
                project_name = project_element.find_element(By.CSS_SELECTOR, "h5.card-title").text.strip()
                promoter = project_element.find_element(By.CSS_SELECTOR, "small").text.strip()
                if promoter.lower().startswith("by "):
                    promoter = promoter[3:].strip()
                
                address = "Not found"
                try:
                    address_element = project_element.find_element(By.XPATH, ".//label[contains(text(), 'Address')]/following-sibling::strong")
                    address = address_element.text.strip()
                except:
                    pass
                
                return {
                    "RERA Regd. No": rera_no,
                    "Project Name": project_name,
                    "Promoter Name": promoter,
                    "Address of the Promoter": address,
                    "GST No": "Not available without detail page"
                }
            except Exception as e:
                print(f"Failed to extract data directly from card: {str(e)}")
                return None
        
        try:
            original_window = driver.current_window_handle
            original_handles = driver.window_handles
            
            view_button = view_buttons[0]
            
            href = view_button.get_attribute('href')
            if href and ('javascript:void' in href or 'javascript:' in href):
                script = """
                var elem = arguments[0];
                var projectId = elem.getAttribute('data-project-id') || 
                               elem.getAttribute('data-id') || 
                               elem.parentNode.getAttribute('data-project-id');
                return projectId;
                """
                project_id = driver.execute_script(script, view_button)
                if project_id:
                    print(f"Extracted project ID {project_id} from JavaScript link")
                
                try:
                    rera_no = project_element.find_element(By.CSS_SELECTOR, "span.fw-bold").text.strip()
                    project_name = project_element.find_element(By.CSS_SELECTOR, "h5.card-title").text.strip()
                    promoter = project_element.find_element(By.CSS_SELECTOR, "small").text.strip()
                    if promoter.lower().startswith("by "):
                        promoter = promoter[3:].strip()
                    
                    address = "Not found"
                    try:
                        address_element = project_element.find_element(By.XPATH, ".//label[contains(text(), 'Address')]/following-sibling::strong")
                        address = address_element.text.strip()
                    except:
                        pass
                    
                    return {
                        "RERA Regd. No": rera_no,
                        "Project Name": project_name,
                        "Promoter Name": promoter,
                        "Address of the Promoter": address,
                        "GST No": "Not available without detail page"
                    }
                except Exception as e:
                    print(f"Error extracting data from card: {str(e)}")
                    
                try:
                    driver.execute_script("arguments[0].click();", view_button)
                except Exception as js_e:
                    print(f"JavaScript click failed: {str(js_e)}")
                    return None
            else:
                driver.execute_script("arguments[0].click();", view_button)
            
            time.sleep(3)
            
            new_handles = driver.window_handles
            if len(new_handles) > len(original_handles):
                new_window = [h for h in new_handles if h not in original_handles][0]
                driver.switch_to.window(new_window)
            
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            handle_popup(driver)
            
        except Exception as e:
            print(f"Error clicking view details button: {str(e)}")
            return None
        
        rera_no = safe_get_element_text(driver, "//th[contains(text(), 'RERA Regd. No')]/following-sibling::td")
        project_name = safe_get_element_text(driver, "//th[contains(text(), 'Project Name')]/following-sibling::td")
        
        try:
           
            selectors = [
                "//a[contains(text(), 'Promoter Details')]",
                "//li/a[contains(text(), 'Promoter')]",
                "//div[contains(@class, 'tab')]/a[contains(text(), 'Promoter')]"
            ]
            
            found_tab = False
            for selector in selectors:
                try:
                    promoter_tab = WebDriverWait(driver, 5).until(
                        EC.element_to_be_clickable((By.XPATH, selector))
                    )
                    driver.execute_script("arguments[0].click();", promoter_tab)
                    found_tab = True
                    print("Clicked on Promoter Details tab")
                    time.sleep(3)
                    break
                except (TimeoutException, NoSuchElementException, ElementClickInterceptedException):
                    continue
            
            if not found_tab:
                print("Could not find or click on Promoter Details tab")
                return {
                    "RERA Regd. No": rera_no,
                    "Project Name": project_name,
                    "Promoter Name": "Tab not found",
                    "Address of the Promoter": "Tab not found",
                    "GST No": "Tab not found"
                }
            
            company_selectors = [
                "//th[contains(text(), 'Company Name')]/following-sibling::td",
                "//th[contains(text(), 'Promoter Name')]/following-sibling::td",
                "//th[contains(text(), 'Name of Promoter')]/following-sibling::td",
                "//th[contains(text(), 'Company')]/following-sibling::td"
            ]
            
            promoter_name = "Not found"
            for selector in company_selectors:
                try:
                    element = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                    promoter_name = element.text.strip()
                    if promoter_name:
                        break
                except (TimeoutException, NoSuchElementException):
                    continue
            
            address_selectors = [
                "//th[contains(text(), 'Registered Office Address')]/following-sibling::td",
                "//th[contains(text(), 'Office Address')]/following-sibling::td",
                "//th[contains(text(), 'Address')]/following-sibling::td"
            ]
            
            address = "Not found"
            for selector in address_selectors:
                try:
                    element = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                    address = element.text.strip()
                    if address:
                        break
                except (TimeoutException, NoSuchElementException):
                    continue
            
            gst_selectors = [
                "//th[contains(text(), 'GST No')]/following-sibling::td",
                "//th[contains(text(), 'GST Number')]/following-sibling::td",
                "//th[contains(text(), 'GSTIN')]/following-sibling::td"
            ]
            
            gst_no = "Not found"
            for selector in gst_selectors:
                try:
                    element = WebDriverWait(driver, 5).until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                    gst_no = element.text.strip()
                    if gst_no:
                        break
                except (TimeoutException, NoSuchElementException):
                    continue
                
        except Exception as e:
            print(f"Error extracting promoter details: {str(e)}")
            promoter_name = "Error occurred"
            address = "Error occurred"
            gst_no = "Error occurred"
        
        if len(driver.window_handles) > 1:
            driver.close()
            driver.switch_to.window(original_window)
        
        return {
            "RERA Regd. No": rera_no,
            "Project Name": project_name,
            "Promoter Name": promoter_name,
            "Address of the Promoter": address,
            "GST No": gst_no
        }
    
    except Exception as e:
        print(f"Error processing project details: {str(e)}")
        try:
            if len(driver.window_handles) > 1:
                driver.close()
                driver.switch_to.window(driver.window_handles[0])
        except:
            pass
        return None

def main():
    """Main function to scrape the RERA Odisha website."""
    url = "https://rera.odisha.gov.in/projects/project-list"
    max_projects = 6
    min_projects = 6  
    driver = setup_driver()
    
    try:
        driver.get(url)
        print("Loading main page...")
        time.sleep(5)  
        
        handle_popup(driver)
        
        project_selectors = [
            "//div[contains(@class, 'project-card')]",
            "//div[contains(@class, 'card') and contains(@class, 'project-card')]",
            "//div[contains(@class, 'container')]/div[contains(@class, 'row')]/div[contains(@class, 'col-lg-4')]",
            "//div[contains(@class, 'card')]"
        ]
        
        project_identifiers = []
        for selector in project_selectors:
            try:
                elements = WebDriverWait(driver, 15).until(
                    EC.presence_of_all_elements_located((By.XPATH, selector))
                )
                for idx, element in enumerate(elements):
                    try:
                        project_id = get_project_id_from_element(element)
                        project_identifiers.append((selector, idx, project_id))
                    except:
                        project_identifiers.append((selector, idx, f"project_{idx}"))
                if project_identifiers:
                    break
            except (TimeoutException, NoSuchElementException):
                continue
        
        if not project_identifiers:
            print("Could not find any projects on the page")
            driver.save_screenshot("no_projects_found.png")
            return
        
        print(f"Found {len(project_identifiers)} projects. Starting to extract details...")
        all_projects_data = []
        
        processed_count = 0
        successful_count = 0
        
        while successful_count < min_projects and processed_count < len(project_identifiers):
            selector, index, project_id = project_identifiers[processed_count]
            processed_count += 1
            
            print(f"\nProcessing project {processed_count} of {len(project_identifiers)} (ID: {project_id})")
            
            try:
                elements = WebDriverWait(driver, 15).until(
                    EC.presence_of_all_elements_located((By.XPATH, selector))
                )
                if len(elements) > index:
                    project_element = elements[index]
                    project_data = scrape_project_details(driver, project_element, processed_count)
                    if project_data:
                        all_projects_data.append(project_data)
                        successful_count += 1
                        print(f"Successfully scraped project {successful_count} of {min_projects}")
                    else:
                        print(f"Project {processed_count} scraping failed, moving to next")
                else:
                    print(f"Project index {index} not found in current elements")
            except StaleElementReferenceException:
                print("Stale element reference, retrying...")
                time.sleep(2)
                driver.refresh()
                time.sleep(3)
                handle_popup(driver)
                continue
            except Exception as e:
                print(f"Error processing project {processed_count}: {str(e)}")
            
            time.sleep(2)
            
            if successful_count >= min_projects:
                break
        
        if successful_count < min_projects:
            print(f"Only {successful_count} projects scraped, attempting to find more projects")
            try:
                new_project_identifiers = []
                for selector in project_selectors:
                    try:
                        elements = WebDriverWait(driver, 10).until(
                            EC.presence_of_all_elements_located((By.XPATH, selector))
                        )
                        for idx, element in enumerate(elements):
                            if idx >= len(project_identifiers) or project_identifiers[idx][0] != selector:
                                try:
                                    project_id = get_project_id_from_element(element)
                                    new_project_identifiers.append((selector, idx, project_id))
                                except:
                                    new_project_identifiers.append((selector, idx, f"project_{idx}"))
                    except:
                        continue
                
                for selector, index, project_id in new_project_identifiers:
                    if successful_count >= min_projects:
                        break
                    
                    print(f"\nProcessing additional project (ID: {project_id})")
                    
                    try:
                        elements = WebDriverWait(driver, 10).until(
                            EC.presence_of_all_elements_located((By.XPATH, selector))
                        )
                        if len(elements) > index:
                            project_element = elements[index]
                            project_data = scrape_project_details(driver, project_element, processed_count+1)
                            if project_data:
                                all_projects_data.append(project_data)
                                successful_count += 1
                                print(f"Successfully scraped additional project {successful_count} of {min_projects}")
                            else:
                                print(f"Additional project scraping failed, moving to next")
                    except Exception as e:
                        print(f"Error processing additional project: {str(e)}")
                    
                    time.sleep(2)
            except Exception as e:
                print(f"Error finding additional projects: {str(e)}")
        
        if all_projects_data:
            df = pd.DataFrame(all_projects_data)
            df.to_csv("output.csv", index=False)
            print(f"Successfully scraped {len(all_projects_data)} projects. Data saved to output.csv")
            
            try:
                df.to_excel("output.xlsx", index=False)
                print("Data also saved to output.xlsx")
            except Exception as e:
                print(f"Could not save Excel file: {str(e)}")
        else:
            print("No project data was collected")
                
    except Exception as e:
        print(f"An error occurred: {str(e)}")
        import traceback
        traceback.print_exc()
    
    finally:
        driver.quit()

if __name__ == "__main__":
    main()