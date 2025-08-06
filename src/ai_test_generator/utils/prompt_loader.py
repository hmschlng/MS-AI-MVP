"""
간단한 프롬프트 로더

YAML 파일에서 프롬프트를 읽어와 문자열 치환을 통해 사용하는 단순한 로더입니다.
"""
import yaml
from pathlib import Path
from typing import Dict, Any
from ai_test_generator.utils.logger import get_logger

logger = get_logger(__name__)


class PromptLoader:
    """프롬프트 YAML 파일 로더"""
    
    def __init__(self, prompts_dir: str = None):
        if prompts_dir:
            self.prompts_dir = Path(prompts_dir)
        else:
            # 프로젝트 루트의 prompts 디렉터리를 가리킴
            self.prompts_dir = Path(__file__).parent.parent.parent.parent / "prompts"
        
        self.prompts_cache = {}
    
    def load_prompt(self, template_name: str) -> Dict[str, Any]:
        """프롬프트 템플릿 로드"""
        if template_name in self.prompts_cache:
            return self.prompts_cache[template_name]
        
        yaml_file = self.prompts_dir / f"{template_name}.yaml"
        
        if not yaml_file.exists():
            logger.error(f"Prompt file not found: {yaml_file}")
            return {"system_prompt": "", "human_prompt": ""}
        
        try:
            with open(yaml_file, 'r', encoding='utf-8') as file:
                data = yaml.safe_load(file)
                self.prompts_cache[template_name] = data
                return data
        except Exception as e:
            logger.error(f"Error loading prompt {template_name}: {e}")
            return {"system_prompt": "", "human_prompt": ""}
    
    def get_prompt(self, template_name: str, **kwargs) -> tuple[str, str]:
        """프롬프트 템플릿에 변수를 치환하여 반환"""
        template = self.load_prompt(template_name)
        
        system_prompt = template.get("system_prompt", "")
        human_prompt = template.get("human_prompt", "")
        
        # 간단한 문자열 치환
        try:
            system_prompt = system_prompt.format(**kwargs)
            human_prompt = human_prompt.format(**kwargs)
        except KeyError as e:
            logger.warning(f"Missing variable in prompt {template_name}: {e}")
        
        return system_prompt, human_prompt