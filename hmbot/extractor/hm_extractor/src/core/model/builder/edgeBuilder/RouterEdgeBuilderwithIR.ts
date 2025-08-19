import { Stmt, ArkMethod, Scene, ArkInvokeStmt, Cfg, ArkAssignStmt, Local } from "../../../../arkanalyzer/src";
import { PageTransitionGraph, PTGNode } from "../../PageTransitionGraph";
import { EdgeBuilderInterface } from "./BasicEdgeBuilder";
import Const from "../../../common/Constant";
import Utils, { MyValue } from "../../../common/Utils";

import { StringConstant } from "../../../../arkanalyzer/src/core/base/Constant";

export class RouterEdgeBuilderwithIR implements EdgeBuilderInterface{
    edgeBuilderStrategy: string = "RouterEdgeBuilderwithIR";
    scene: Scene;
    ptg:PageTransitionGraph;

    constructor(scene: Scene, ptg: PageTransitionGraph){
        this.scene = scene;
        this.ptg = ptg;
    }
    identifyPTGEdge(ptgNode: PTGNode, method: ArkMethod): void {
        const cfg = method.getBody()?.getCfg();
        for(const unit of method.getCfg()!.getStmts()) {
            this.identifyPTGEdgeByIRAnalysis(ptgNode, unit, cfg!,  method);
        }
    }

    /**
     * 根据page迁移语句识别PTGEdge
     * 通过字节码分析
     * @param ptgNode 
     * @param unit 
     * @param cfg 
     * @param method 
     */
    identifyPTGEdgeByIRAnalysis(ptgNode: PTGNode, unit: Stmt, cfg: Cfg, method: ArkMethod) {
        // console.log("identify PTG edge by IR analysis");
        // 获取ptgNode所属的类名
        const caller = ptgNode.getClassOfPage().toString();
        let callee = "";
        // 判断unit是否为ArkInvokeStmt类型
        if(unit instanceof ArkInvokeStmt) {
            let expr = unit.getInvokeExpr();
            let invokeMethod = expr.getMethodSignature();
            const invokeMethodName = invokeMethod.getMethodSubSignature().getMethodName();
            // 判断调用表达式的方法名是否为pushUrl或replaceUrl
            for( let entry of Const.ROUTERTRANSTIONSTMTS.entries()){
                if(entry[0] == invokeMethodName){
                    // 获取cfg的def-use链
                    cfg?.buildDefUseChain(); 
                    const chains = cfg?.getDefUseChains();

                    // 获取 pageTargetVar的对象（匿名类）名称
                    let pageTargetVarLoction = entry[1];
                    let pageTargetVarName = ""; 
                    if(chains != undefined){
                        for (const chain of chains){
                            if(chain.value == expr.getArg(pageTargetVarLoction)){
                                if(chain.def instanceof ArkAssignStmt){
                                    pageTargetVarName = chain.def.getRightOp().getType().toString();
                                    break;
                                }
                            }
                        }
                    }  
                    // 获取 pageTargetVar的取值
                    const pageTargetFieldValue = Utils.getValueOfClassFiled(this.scene, pageTargetVarName, Const.PAGETARGETOBJNAME);
                    let pageTargetValue = pageTargetFieldValue;
                    if(pageTargetValue != undefined){
                        //for local variable, get its concrete value first
                        if(pageTargetValue instanceof Local){
                            pageTargetValue = Utils.getValueOfVar(method, pageTargetValue, new MyValue())?.value
                        }
                        //获取目标页面类的名字
                        if(pageTargetValue instanceof StringConstant){
                            let targetPageName  = (pageTargetValue as StringConstant).getValue()
                            // callee = Utils.getComponentClassOfPage(this.scene, targetPageName)!.getSignature().toString();
                        }
                        this.ptg.addPTGEdgeByName(caller, callee, unit);
                    }
                }

            }
        }
    }
    
}