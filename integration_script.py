"""
Integration script to help upgrade your Cleo chatbot with improved prompts
"""

import json
import shutil
from datetime import datetime

def backup_current_prompts():
    """Create a backup of the current prompts.py file"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_filename = f"prompts_backup_{timestamp}.py"
    
    try:
        shutil.copy("prompts.py", backup_filename)
        print(f"✅ Backup created: {backup_filename}")
        return True
    except Exception as e:
        print(f"❌ Failed to create backup: {e}")
        return False

def load_training_data():
    """Load the generated training data"""
    try:
        with open("cleo_training_data.json", 'r', encoding='utf-8') as f:
            data = json.load(f)
        print("✅ Training data loaded successfully")
        return data
    except Exception as e:
        print(f"❌ Failed to load training data: {e}")
        return None

def show_improvement_summary(training_data):
    """Show a summary of the improvements available"""
    print("\n" + "="*60)
    print("🎯 CLEO CHATBOT IMPROVEMENT SUMMARY")
    print("="*60)
    
    print(f"\n📊 Training Data Generated:")
    print(f"   - {len(training_data['conversation_examples'])} conversation examples")
    print(f"   - {len(training_data['scoring_examples'])} scoring examples")
    print(f"   - {len(training_data['training_scenarios'])} training scenarios")
    print(f"   - {len(training_data['optimized_prompts'])} optimized prompts")
    
    print(f"\n🚀 Key Improvements Available:")
    print("   1. More natural and engaging conversation flow")
    print("   2. Better handling of hesitant candidates")
    print("   3. Improved scoring accuracy with edge cases")
    print("   4. Enhanced error handling and clarification")
    print("   5. More professional and warm tone")
    
    print(f"\n💡 Best Practices Included:")
    for practice in training_data['best_practices']['conversation_flow']:
        print(f"   - {practice}")
    
    print(f"\n🔧 Integration Options:")
    print("   1. Replace current prompts with improved versions")
    print("   2. Test improved prompts alongside current ones")
    print("   3. Gradual migration with A/B testing")
    print("   4. Custom integration based on specific needs")

def show_conversation_examples(training_data):
    """Show example conversations from training data"""
    print("\n" + "="*60)
    print("💬 CONVERSATION EXAMPLES")
    print("="*60)
    
    for i, example in enumerate(training_data['conversation_examples'], 1):
        print(f"\n📝 Example {i}: {example['scenario'].replace('_', ' ').title()}")
        print("-" * 40)
        
        for msg in example['conversation'][:4]:  # Show first 4 messages
            role = "🤖 Cleo" if msg['role'] == 'assistant' else "👤 Candidate"
            print(f"{role}: {msg['content']}")
        
        if len(example['conversation']) > 4:
            print("   ... (conversation continues)")

def show_scoring_examples(training_data):
    """Show scoring examples from training data"""
    print("\n" + "="*60)
    print("📊 SCORING EXAMPLES")
    print("="*60)
    
    for i, example in enumerate(training_data['scoring_examples'], 1):
        print(f"\n🎯 Example {i}:")
        print(f"   Question: {example['question']}")
        print(f"   Answer: {example['answer']}")
        print(f"   Expected Score: {example['expected_score']}")
        print(f"   Reasoning: {example['reasoning']}")

def show_optimized_prompts(training_data):
    """Show the optimized prompts"""
    print("\n" + "="*60)
    print("🔧 OPTIMIZED PROMPTS")
    print("="*60)
    
    for prompt_name, prompt_content in training_data['optimized_prompts'].items():
        print(f"\n📝 {prompt_name.replace('_', ' ').title()}:")
        print("-" * 40)
        print(prompt_content[:200] + "..." if len(prompt_content) > 200 else prompt_content)

def create_integration_plan():
    """Create a step-by-step integration plan"""
    print("\n" + "="*60)
    print("📋 INTEGRATION PLAN")
    print("="*60)
    
    plan = [
        "1. Backup your current prompts.py file",
        "2. Review the improved prompts in prompts_improved.py",
        "3. Test the improved prompts in a development environment",
        "4. Compare performance with current prompts",
        "5. Gradually integrate improved prompts",
        "6. Monitor chatbot performance and user feedback",
        "7. Iterate and improve based on real-world usage"
    ]
    
    for step in plan:
        print(f"   {step}")
    
    print(f"\n🎯 Recommended Next Steps:")
    print("   1. Run: python integration_script.py --backup")
    print("   2. Review prompts_improved.py")
    print("   3. Test with: python main.py")
    print("   4. Compare performance metrics")

def main():
    """Main integration script"""
    print("🤖 Cleo Chatbot Integration Script")
    print("="*50)
    
    # Load training data
    training_data = load_training_data()
    if not training_data:
        return
    
    # Show improvement summary
    show_improvement_summary(training_data)
    
    # Show examples
    show_conversation_examples(training_data)
    show_scoring_examples(training_data)
    show_optimized_prompts(training_data)
    
    # Create integration plan
    create_integration_plan()
    
    print(f"\n🎉 Integration script completed!")
    print(f"📁 Files created:")
    print(f"   - prompts_improved.py (improved prompts)")
    print(f"   - cleo_training_data.json (training dataset)")
    print(f"   - integration_script.py (this script)")

if __name__ == "__main__":
    main()
