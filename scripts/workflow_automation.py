#!/usr/bin/env python3
"""
Automated Lead Generation Workflow
Integrates lead qualification with your existing CRM and email system

This script orchestrates the entire lead-to-outreach pipeline:
1. Qualify leads from raw CSV
2. Update Google Sheets CRM
3. Generate research briefs (optional)
4. Prepare for email outreach

Usage:
    python scripts/automated_workflow.py --input data/raw_leads.csv --target 30
    
For Claude Code:
    Just say: "Run the automated workflow to qualify 30 leads"
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path
from datetime import datetime
import pandas as pd

# Color codes for terminal output
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'
    BOLD = '\033[1m'


def print_header(text):
    """Print formatted header"""
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{text}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*70}{Colors.END}\n")


def print_success(text):
    """Print success message"""
    print(f"{Colors.GREEN}✅ {text}{Colors.END}")


def print_error(text):
    """Print error message"""
    print(f"{Colors.RED}❌ {text}{Colors.END}")


def print_info(text):
    """Print info message"""
    print(f"{Colors.CYAN}ℹ️  {text}{Colors.END}")


def print_warning(text):
    """Print warning message"""
    print(f"{Colors.YELLOW}⚠️  {text}{Colors.END}")


def run_command(command, description, critical=True):
    """
    Run a shell command and handle errors
    
    Args:
        command: Command to run (string or list)
        description: What this command does
        critical: If True, exit on error. If False, continue.
    
    Returns:
        bool: True if successful, False otherwise
    """
    print(f"\n{Colors.CYAN}🔄 {description}...{Colors.END}")
    
    try:
        if isinstance(command, str):
            result = subprocess.run(
                command,
                shell=True,
                check=True,
                capture_output=True,
                text=True
            )
        else:
            result = subprocess.run(
                command,
                check=True,
                capture_output=True,
                text=True
            )
        
        # Print output
        if result.stdout:
            print(result.stdout)
        
        print_success(f"{description} complete")
        return True
    
    except subprocess.CalledProcessError as e:
        print_error(f"{description} failed")
        print(f"\nError output:\n{e.stderr}")
        
        if critical:
            print_error("Critical step failed. Exiting workflow.")
            sys.exit(1)
        else:
            print_warning("Non-critical step failed. Continuing...")
            return False
    
    except Exception as e:
        print_error(f"Unexpected error: {e}")
        if critical:
            sys.exit(1)
        return False


def verify_file_exists(filepath, description):
    """Verify a file exists"""
    if not os.path.exists(filepath):
        print_error(f"{description} not found: {filepath}")
        return False
    
    print_success(f"{description} found: {filepath}")
    return True


def get_file_stats(filepath):
    """Get statistics about a CSV file"""
    try:
        df = pd.read_csv(filepath)
        return {
            'total_rows': len(df),
            'columns': list(df.columns),
            'qualified': len(df[df.get('Status', '') == 'QUALIFIED']) if 'Status' in df.columns else 0
        }
    except Exception as e:
        print_warning(f"Could not read file stats: {e}")
        return None


class WorkflowOrchestrator:
    """Orchestrate the complete lead generation workflow"""

    def __init__(self,
                 target_count: int,
                 output_dir: str = "data",
                 skip_crm: bool = False,
                 db_path: str = "data/leads_v3.db"):

        self.target_count = target_count
        self.output_dir = output_dir
        self.skip_crm = skip_crm
        self.db_path = db_path

        # Generate timestamped filenames
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        self.qualified_file = os.path.join(output_dir, f"qualified_leads_{timestamp}.csv")
        self.report_file = os.path.join(output_dir, f"workflow_report_{timestamp}.txt")

        self.results = {}
    
    def run(self):
        """Execute the complete workflow"""

        print_header("🚀 AUTOMATED LEAD GENERATION WORKFLOW (V3)")

        print(f"{Colors.BOLD}Configuration:{Colors.END}")
        print(f"  💾 Database:      {self.db_path}")
        print(f"  🎯 Target:        {self.target_count} qualified leads")
        print(f"  📂 Output:        {self.qualified_file}")
        print(f"  📊 Report:        {self.report_file}")
        print()

        # Step 1: Run lead generation and qualification
        success = self._run_lead_qualifier()
        if not success:
            return False

        # Step 2: Verify output
        success = self._verify_output()
        if not success:
            return False

        # Step 3: Update CRM (if enabled)
        if not self.skip_crm:
            self._update_crm()
        else:
            print_info("Skipping CRM update (--skip-crm flag)")

        # Step 4: Generate report
        self._generate_report()

        # Step 5: Next steps
        self._print_next_steps()

        return True
    
    def _run_lead_qualifier(self):
        """Run the lead qualification script"""

        # Use the v3 pipeline which includes validation
        command = [
            './generate_v3',
            str(self.target_count)
        ]

        success = run_command(
            command,
            f"Generating and qualifying {self.target_count} leads",
            critical=True
        )

        if success:
            # Export qualified leads to CSV
            export_command = [
                'python',
                'scripts/export_qualified_leads.py',
                '--target', str(self.target_count),
                '--output', self.qualified_file
            ]

            return run_command(
                export_command,
                "Exporting qualified leads to CSV",
                critical=True
            )

        return False
    
    def _verify_output(self):
        """Verify the qualified leads file was created"""
        
        print_header("📊 VERIFICATION")
        
        # Check qualified file
        if not verify_file_exists(self.qualified_file, "Qualified leads file"):
            return False
        
        # Get stats
        stats = get_file_stats(self.qualified_file)
        if not stats:
            return False
        
        self.results['qualified_count'] = stats['total_rows']
        
        print(f"\n{Colors.BOLD}Results:{Colors.END}")
        print(f"  ✅ Qualified leads: {stats['total_rows']}")
        
        if stats['total_rows'] < self.target_count:
            shortfall = self.target_count - stats['total_rows']
            print_warning(f"Only found {stats['total_rows']}/{self.target_count} qualified leads")
            print(f"     Missing: {shortfall} leads")
            print(f"\n{Colors.YELLOW}💡 Suggestions:{Colors.END}")
            print("     • Expand search to nearby cities")
            print("     • Relax employee count criteria")
            print("     • Include more industries")
        elif stats['total_rows'] > self.target_count:
            print_success(f"Found {stats['total_rows']} leads (exceeded target by {stats['total_rows'] - self.target_count})")
        else:
            print_success(f"Perfect! Found exactly {self.target_count} qualified leads")
        
        # Check excluded file
        if verify_file_exists(self.excluded_file, "Excluded leads file"):
            excluded_stats = get_file_stats(self.excluded_file)
            if excluded_stats:
                self.results['excluded_count'] = excluded_stats['total_rows']
                print(f"  📋 Excluded leads: {excluded_stats['total_rows']}")
        
        return True
    
    def _update_crm(self):
        """Update Google Sheets CRM with qualified leads"""
        
        print_header("📈 CRM UPDATE")
        
        # Check if prospects_tracker.py exists
        tracker_script = 'scripts/prospects_tracker.py'
        
        if not os.path.exists(tracker_script):
            print_warning(f"CRM script not found: {tracker_script}")
            print_info("Skipping CRM update")
            return False
        
        # Check for credentials
        if not os.path.exists('credentials.json'):
            print_warning("credentials.json not found")
            print_info("Skipping CRM update. Set up Google Sheets API first.")
            return False
        
        # Run CRM update
        return run_command(
            ['python', tracker_script],
            "Updating Google Sheets CRM",
            critical=False  # Not critical if it fails
        )
    
    def _generate_report(self):
        """Generate a workflow summary report"""
        
        print_header("📝 GENERATING REPORT")
        
        report_lines = []
        report_lines.append("=" * 70)
        report_lines.append("LEAD GENERATION WORKFLOW REPORT")
        report_lines.append("=" * 70)
        report_lines.append(f"\nDate: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        report_lines.append(f"\nConfiguration:")
        report_lines.append(f"  Input File:    {self.input_file}")
        report_lines.append(f"  Target Count:  {self.target_count}")
        report_lines.append(f"  Output File:   {self.qualified_file}")
        
        report_lines.append(f"\nResults:")
        report_lines.append(f"  Qualified:     {self.results.get('qualified_count', 0)}")
        report_lines.append(f"  Excluded:      {self.results.get('excluded_count', 0)}")
        
        success_rate = 0
        total = self.results.get('qualified_count', 0) + self.results.get('excluded_count', 0)
        if total > 0:
            success_rate = (self.results.get('qualified_count', 0) / total) * 100
        
        report_lines.append(f"  Success Rate:  {success_rate:.1f}%")
        
        report_lines.append(f"\nFiles Generated:")
        report_lines.append(f"  • {self.qualified_file}")
        report_lines.append(f"  • {self.excluded_file}")
        
        report_lines.append(f"\nNext Steps:")
        report_lines.append(f"  1. Review qualified_leads file")
        report_lines.append(f"  2. Research top 10 prospects")
        report_lines.append(f"  3. Generate personalized emails")
        report_lines.append(f"  4. Begin outreach campaign")
        
        report_lines.append("\n" + "=" * 70)
        
        # Write to file
        report_content = "\n".join(report_lines)
        
        try:
            with open(self.report_file, 'w') as f:
                f.write(report_content)
            print_success(f"Report saved: {self.report_file}")
        except Exception as e:
            print_warning(f"Could not save report: {e}")
        
        # Print to console
        print("\n" + report_content)
    
    def _print_next_steps(self):
        """Print recommended next steps"""
        
        print_header("🎯 NEXT STEPS")
        
        print(f"{Colors.BOLD}Recommended workflow:{Colors.END}\n")
        
        print(f"{Colors.GREEN}1. Review qualified leads{Colors.END}")
        print(f"   Open: {self.qualified_file}")
        print(f"   Verify data quality and company fit\n")
        
        print(f"{Colors.GREEN}2. Research top prospects{Colors.END}")
        print(f"   Command: python scripts/generate_research.py")
        print(f"   Focus on the top 10-15 companies\n")
        
        print(f"{Colors.GREEN}3. Generate personalized emails{Colors.END}")
        print(f"   Use Claude AI to create custom outreach")
        print(f"   Command: python scripts/email_generator.py\n")
        
        print(f"{Colors.GREEN}4. Launch outreach campaign{Colors.END}")
        print(f"   Command: python scripts/email_sender.py --dry-run")
        print(f"   Then: python scripts/email_sender.py\n")
        
        print(f"{Colors.CYAN}💡 Pro tip:{Colors.END}")
        print(f"   Use Claude Code to automate: 'Run the complete workflow from qualified leads to sent emails'\n")


def main():
    """Command-line interface"""
    
    parser = argparse.ArgumentParser(
        description='Automated lead generation workflow',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage - qualify 30 leads
  python scripts/automated_workflow.py --input data/raw_leads.csv --target 30
  
  # With Claude Code
  claude-code
  > Run the automated workflow to qualify 40 leads from data/hamilton_leads.csv
  
  # Skip CRM update (if not configured yet)
  python scripts/automated_workflow.py --input data/leads.csv --target 30 --skip-crm
        """
    )
    
    parser.add_argument(
        '--target',
        type=int,
        default=30,
        help='Number of qualified leads needed (default: 30)'
    )

    parser.add_argument(
        '--db',
        type=str,
        default='data/leads_v3.db',
        help='Database path (default: data/leads_v3.db)'
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        default='data',
        help='Output directory for results (default: data/)'
    )
    
    parser.add_argument(
        '--skip-crm',
        action='store_true',
        help='Skip Google Sheets CRM update'
    )
    
    args = parser.parse_args()
    
    # Create output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Run workflow
    orchestrator = WorkflowOrchestrator(
        target_count=args.target,
        output_dir=args.output_dir,
        skip_crm=args.skip_crm,
        db_path=args.db
    )
    
    success = orchestrator.run()
    
    if success:
        print(f"\n{Colors.BOLD}{Colors.GREEN}✅ Workflow completed successfully!{Colors.END}\n")
        sys.exit(0)
    else:
        print(f"\n{Colors.BOLD}{Colors.RED}❌ Workflow failed. Check errors above.{Colors.END}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
